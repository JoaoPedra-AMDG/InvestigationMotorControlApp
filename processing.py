"""Process original steady-state samples and compare compatible acquisitions."""
import csv
import io
import json
import math
from experiment import atomic_json,read_json


def process_results(store,settings):
    processed=[];excluded=[]
    # Use the same duration across eligible captures: additional sensorless
    # channels reduce the finite buffer length, otherwise biasing maxima.
    windows=[]
    for run in store.list_runs():
        if run['status'] in ('recording','processing','invalid-acquisition','unsuccessful') or run['plan']['test_type']!='steady state':continue
        for name in reversed(run['datasets']):
            rows,meta=store.load_dataset(run['id'],name)
            if meta.get('role','test')=='test' and meta.get('source')!='SIMULATION' and len(rows)>2 and all(r.get('time_s') is not None for r in rows) and all(any(r.get(k) is not None for r in rows) for k in ('ia_a','ib_a','ic_a')):
                if rows[-1]['time_s']>rows[0]['time_s']:windows.append(rows[-1]['time_s']-rows[0]['time_s'])
                break
    common_duration=min(windows) if windows else None
    for run in sorted(store.list_runs(),key=lambda r:(r.get('created_utc',''),r['id'])):
        reason=None
        if run['status'] in ('recording','processing'):reason='Still recording or downloading'
        elif run['plan']['test_type']!='steady state':reason='Not a steady-state test'
        elif run['status'] in ('invalid-acquisition','unsuccessful') or run['acquisition_status'] in ('invalid','interrupted') or run['control_outcome']=='failure':reason='Acquisition or control failure'
        if reason:excluded.append({'run_id':run['id'],'reason':reason});continue
        candidates=[]
        for name in reversed(run['datasets']):
            rows,meta=store.load_dataset(run['id'],name)
            if meta.get('role','test')!='test' or meta.get('source')=='SIMULATION':continue
            if all(any(r.get(key) is not None for r in rows) for key in ('ia_a','ib_a','ic_a')):
                candidates.append((name,rows,meta))
        if not candidates:excluded.append({'run_id':run['id'],'reason':'No test-motor high-rate phase-current dataset'});continue
        name,rows,meta=candidates[0]
        config=dict(settings,window_type='steady state')
        if common_duration is not None and settings.get('start_s') is None and settings.get('end_s') is None:
            config.update(start_s=rows[0]['time_s'],end_s=rows[0]['time_s']+common_duration)
        speeds=[r['drive_rotor_rpm'] for r in rows if isinstance(r.get('drive_rotor_rpm'),(int,float)) and math.isfinite(r['drive_rotor_rpm'])]
        if speeds and any(abs(s-run['plan']['rpm']*meta.get('profile',{}).get('test_direction',1))>run['plan']['settle_rpm'] for s in speeds):
            excluded.append({'run_id':run['id'],'reason':'Captured speed left the steady-state tolerance'});continue
        if not config.get('fundamental_hz'):
            pp=meta.get('pole_pairs') or meta.get('calibration',{}).get('pole_pairs')
            speeds=[abs(r['drive_rotor_rpm']) for r in rows if isinstance(r.get('drive_rotor_rpm'),(int,float)) and math.isfinite(r['drive_rotor_rpm'])]
            if pp and speeds:
                config['fundamental_hz']=sum(speeds)/len(speeds)*pp/60
                config['fundamental_basis']='Mean captured rotor speed times configured pole pairs; constant steady-state fundamental.'
            elif run.get('latest_review') and run['latest_review']['dataset']==name:
                previous=run['latest_review']['summary'].get('settings',{})
                if previous.get('fundamental_hz'):
                    config['fundamental_hz']=previous['fundamental_hz']
                    config['fundamental_basis']='Previously declared frequency for this dataset in revision '+run['latest_review']['id']
        try:
            result=store.review(run['id'],name,config)
            metric=result['metrics'].get('maximum_current_ripple_a')
            if not result['valid_acquisition'] or not metric:
                reason='; '.join(f['message'] for f in result['quality_flags'] if f['severity']!='info') or 'Ripple metric unavailable'
                excluded.append({'run_id':run['id'],'reason':reason});continue
            acq=meta.get('acquisition',{});device=meta.get('device',{})
            # Do not pool different instruments, rates, bandwidths or filtering.
            comparison={k:acq.get(k) for k in ('source','bandwidth_hz','filtering')}
            comparison['sample_hz']=acq.get('native_control_loop_hz') or acq.get('requested_hz')
            comparison.update(serial=device.get('serial') or meta.get('operator_declaration',{}).get('device_serials'),firmware=device.get('firmware') or meta.get('operator_declaration',{}).get('firmware'),calibration=meta.get('calibration',{}).get('id'),
                instrument=meta.get('operator_declaration',{}).get('instrument'),window_start=settings.get('start_s'),window_end=settings.get('end_s'),
                common_duration_s=common_duration if settings.get('start_s') is None and settings.get('end_s') is None else None,
                pole_pairs=meta.get('pole_pairs') or meta.get('calibration',{}).get('pole_pairs'))
            raw=raw_peak_to_peak(rows,config.get('start_s'),config.get('end_s'))
            plan=run['plan'];load=plan.get('load',plan.get('load_a'));unit=plan.get('load_unit','A')
            processed.append({'run_id':run['id'],'dataset':name,'analysis_id':store.run(run['id'])['latest_review']['id'],
                'method':plan['method'],'rpm':plan['rpm'],'load':load,'load_unit':unit,'load_a':load if unit=='A' else None,
                'test_id':plan.get('test_id',''),'raw_peak_to_peak':raw,
                'repeat':run['plan']['repeat'],'pair_id':run['plan'].get('pair_id',run['plan_id']),
                'peak_to_peak':metric['peak_to_peak'],'abs_peak':metric['abs_peak'],
                'accepted':run['status']=='completed','comparison_key':json.dumps(comparison,sort_keys=True),'comparison':comparison})
        except (ValueError,TypeError,KeyError,OSError) as exc:excluded.append({'run_id':run['id'],'reason':str(exc)})
    # One latest successfully processed attempt per independent planned repeat.
    unique={}
    for row in processed:unique[(row['pair_id'],row['repeat'],row['method'],row['comparison_key'])]=row
    report={'definition':'raw_peak_to_peak: largest (max - min) of the original phase A/B/C samples in the analysis window. '
        'peak_to_peak: largest peak-to-peak residual across phases after a least-squares fit of DC + the fundamental '
        '(speed x pole pairs) is removed. abs_peak: largest absolute residual. Each plotted point is the maximum across '
        'valid independent repeats of the same point.',
        'limitations':['Raw peak-to-peak includes the fundamental, so it grows with load current; it is not ripple on its own.',
            'Residual metrics assume a constant steady-state fundamental; speed variation leaks into the residual.',
            'Onboard capture runs at the control-loop rate, so PWM-frequency ripple is not resolved; results are not a PWM-ripple measurement.',
            'Each board is captured on its own clock; test/load buffers are not synchronized.',
            'Current-channel bandwidth and filtering are as declared by the operator, not measured by the app.'],
        'rows':list(unique.values()),'excluded':excluded,'settings':settings,
        'note':f'Common analysis duration: {common_duration:.6g} s. Quality-passing data; operator acceptance reported separately. Missing results remain gaps. No PWM-bandwidth claim.' if common_duration else 'No eligible phase-current captures.'}
    atomic_json(store.root/'ripple-results.json',report)
    return report


def raw_peak_to_peak(rows,start=None,end=None):
    """Largest max-min of the original phase-current samples inside [start, end); None if unavailable."""
    best=None
    for key in ('ia_a','ib_a','ic_a'):
        values=[r[key] for r in rows if isinstance(r.get(key),(int,float)) and math.isfinite(r[key])
            and (start is None or r['time_s']>=start) and (end is None or r['time_s']<end)]
        if len(values)>=3:
            spread=max(values)-min(values);best=spread if best is None else max(best,spread)
    return best


def results(store):
    path=store.root/'ripple-results.json'
    return read_json(path) if path.exists() else {'rows':[],'excluded':[],'definition':'Process recorded high-rate datasets to compare ripple at each load.'}


def results_csv(store):
    stream=io.StringIO(newline='');fields=['run_id','test_id','dataset','analysis_id','method','rpm','load','load_unit','repeat','raw_peak_to_peak','peak_to_peak','abs_peak','accepted','comparison_key']
    writer=csv.DictWriter(stream,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(results(store)['rows'])
    return stream.getvalue().encode('utf-8')
