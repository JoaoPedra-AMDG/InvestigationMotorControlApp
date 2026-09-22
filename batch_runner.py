"""One explicitly requested queue; never resumes motion on application restart."""
import copy
import time
from experiment import atomic_json,read_json


class BatchRunner:
    def __init__(self,rig):
        self.rig=rig;self.path=rig.output/'batch.json'
        self.data=read_json(self.path) if self.path.exists() else {'state':'idle','items':[],'current':None,'reason':''}
        self.wait_since=None
        if self.data['state'] in ('running','paused'):
            self.data.update(state='paused',reason='Application restarted. Review interrupted runs; motion will not resume automatically.')
            self.save()

    def save(self):atomic_json(self.path,self.data)
    def snapshot(self):return copy.deepcopy(self.data)
    def reserved(self):return self.data['state'] in ('running','paused')

    def start(self,ids):
        if self.reserved():raise ValueError('Cancel or resume the existing batch first.')
        if self.rig.starting or self.rig.recording or self.rig.automated_point or self.rig.capture_pending:raise ValueError('Finish the active test first.')
        plans=[self.rig.store.plan(i) for i in dict.fromkeys(ids)]
        if not plans:raise ValueError('No pending selected tests to run.')
        if any(p['status']!='pending' for p in plans):raise ValueError('Batch contains a previously run or skipped point.')
        self.data={'state':'running','current':None,'reason':'','pause_requested':False,
            'items':[{'id':p['id'],'state':'queued','phase':'queued','run_id':None} for p in plans]}
        self.wait_since=None;self.save()
        return self.snapshot()

    def pause(self,reason):
        if self.reserved():self.data.update(state='paused',reason=reason);self.save()

    def cancel(self):
        if self.reserved():
            for item in self.data['items']:
                if item['state'] in ('queued','blocked','running'):item['state']='cancelled'
            self.data.update(state='cancelled',reason='Stopped by operator',current=None);self.save()

    def request_pause(self):
        """Finish the test in progress (settle, record, stop), then pause before the next one."""
        if self.data['state']!='running':raise ValueError('No running batch to pause.')
        if self.data['current'] is None:self.pause('Paused by operator.')
        else:self.data['pause_requested']=True;self.save()
        return self.snapshot()

    def _item(self,item_id):
        item=next((i for i in self.data['items'] if i['id']==item_id),None)
        if item is None:raise ValueError('That test is not in the current batch.')
        return item

    def retry(self,item_id):
        """Queue a new attempt of a failed or blocked point directly after it; the failed run is kept."""
        if self.data['state']!='paused':raise ValueError('Pause the batch before retrying a test.')
        item=self._item(item_id)
        if item['state'] not in ('failed','blocked'):raise ValueError('Only failed or blocked tests can be retried.')
        old=self.rig.store.plan(item_id)
        if old['status']=='pending':
            new_id=old['id']
        else:
            fields={k:v for k,v in old.items() if k not in ('id','status','reason','pair_id','matrix_id','retry_of')}
            existing=self.rig.store.test_ids();base=old.get('test_id') or old['id'][-8:];n=2
            while f'{base}-A{n}' in existing:n+=1
            fields['test_id']=f'{base}-A{n}' if old.get('test_id') else ''
            new=self.rig.store.edit_plan(fields)
            new.update(pair_id=old.get('pair_id'),retry_of=old['id']);self.rig.store.save_plans();new_id=new['id']
        index=self.data['items'].index(item)
        item['state']='retried' if new_id!=item_id else 'queued'
        if new_id!=item_id:self.data['items'].insert(index+1,{'id':new_id,'state':'queued','phase':'queued','run_id':None})
        self.save();return self.snapshot()

    def skip(self,item_id,reason):
        if self.data['state']!='paused':raise ValueError('Pause the batch before skipping a test.')
        if not str(reason).strip():raise ValueError('Give a reason for skipping.')
        item=self._item(item_id)
        if item['state'] not in ('failed','blocked','queued'):raise ValueError('Only failed, blocked or queued tests can be skipped.')
        plan=self.rig.store.plan(item_id)
        if plan['status']=='pending':self.rig.store.skip([item_id],reason)
        item.update(state='skipped',phase='skipped',skip_reason=str(reason)[:500]);self.save();return self.snapshot()

    def resume(self):
        if self.data['state']!='paused':raise ValueError('No paused batch.')
        if self.data['current'] is not None:raise ValueError('The interrupted point needs review and a new attempt. Cancel this queue first.')
        undecided=[i['id'] for i in self.data['items'] if i['state']=='failed']
        if undecided:raise ValueError('Retry or skip each failed test before resuming.')
        self.data.update(state='running',reason='');self.wait_since=None;self.save();return self.snapshot()

    def tick(self):
        rig=self.rig
        with rig.lock:
            if self.data['state']!='running':return
            current=self.data['current']
            if current:
                item=next(i for i in self.data['items'] if i['id']==current)
                if rig.active_run and rig.store.run(rig.active_run)['plan_id']==current:item['run_id']=rig.active_run
                if rig.automated_point or rig.starting or rig.capture_pending:
                    if item['phase']!=rig.run_phase:item['phase']=rig.run_phase;self.save()
                    return
                run=rig.store.run(item['run_id']) if item['run_id'] else None
                if rig.run_phase=='failed' or not run or run['acquisition_status']=='invalid' or run['control_outcome']=='failure':
                    item.update(state='failed',phase='failed');self.data['current']=None;self.data['pause_requested']=False
                    self.pause(rig.error or 'Test failed. Review it, then Retry or Skip it explicitly.');return
                item.update(state='recorded',phase='awaiting review');self.data['current']=None;self.wait_since=time.monotonic();self.save()
                if self.data.get('pause_requested'):
                    self.data['pause_requested']=False;self.pause('Paused after the current test, as requested.');return
            item=next((i for i in self.data['items'] if i['state'] in ('queued','blocked')),None)
            if not item:self.data.update(state='complete',reason='All queued tests recorded; processing and review remain available.');self.save();return
            h=rig.hardware.snapshot()
            if not all(b.get('connected') for b in h['boards'].values()):
                item.update(state='blocked',phase='blocked');self.pause('Connect both boards before running the queue.');return
            if h['acquired_at_s'] is None or time.perf_counter()-h['acquired_at_s']>=1 or h['state']=='FAULT':
                item.update(state='blocked',phase='blocked');self.pause('Resolve stale feedback or board faults before resuming.');return
            stationary=all(b.get('state')=='IDLE' and b['signals'].get('speed_rpm') is not None and abs(b['signals']['speed_rpm'])<=5 for b in h['boards'].values())
            if not stationary:
                self.wait_since=self.wait_since or time.monotonic()
                if time.monotonic()-self.wait_since>30:self.pause('Both motors must report IDLE and less than 5 rpm before the next point.')
                return
            next_id=item['id']
        try:rig.action({'action':'run_test','id':next_id},from_batch=True)
        except Exception as exc:
            with rig.lock:
                if self.data['state']=='running':item.update(state='blocked',phase='blocked');self.pause(str(exc))
            return
        with rig.lock:
            if self.data['state']=='running':item.update(state='running',phase='settling');self.data['current']=next_id;self.wait_since=None;self.save()
