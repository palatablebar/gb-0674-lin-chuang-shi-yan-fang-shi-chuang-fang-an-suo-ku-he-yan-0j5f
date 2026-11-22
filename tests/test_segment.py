from app.modules.segment.rules import adjudicate
from app.modules.windows.rules import calculate
from app.modules.archive.rules import freeze
from app.engine import evaluate
from app.config import ROOT
from copy import deepcopy
import pytest

SEGMENT_CSV=(ROOT/'sample_data/segment.csv').read_text()
BROKEN=SEGMENT_CSV.replace('SEGMENT,00001-V1,1.2,g/L,auto,1','SEGMENT,00001-V1,1.2,g/L,v1,1')

def client(tmp_path,monkeypatch):
    from fastapi.testclient import TestClient
    from app import main
    monkeypatch.setattr(main,'DB_PATH',str(tmp_path/'test.sqlite'));return TestClient(main.app)

def segments_of(state):
    return [dict(r) for r in state['records'] if r['kind']=='SEGMENT']

def test_segment_dataset_lockable(segment):
    assert segment['balance']['status']=='可锁库'
    assert segment['balance']['completed']==segment['balance']['expected']==40
    assert segment['archive']['status']=='可冻结'

def test_adopted_date_and_version(segment):
    c=next(r for r in segment['segment_conclusions'] if r['subject']=='00001')
    assert c['adopted_date']=='2026-10-10';assert c['adopted_protocol']=='v2'
    assert c['first_protocol']=='v1';assert c['continuation_protocol']=='v2'
    assert c['version_fallback']=='否';assert c['status']=='已裁决'

def test_segment_counts_one_expected_visit(segment):
    rows=[r for r in segment['completed'] if r['subject']=='00001' and r['visit']=='V1']
    assert len(rows)==1 and rows[0]['id']=='00001-V1'
    assert segment['balance']['expected']==40

def test_segment_window_shared(segment):
    w=next(r for r in segment['windows'] if r['id']=='00001-V1' and r['kind']=='PRIMARY')
    assert w['day']==9 and w['code']=='IN_WINDOW' and w['selected_protocol']=='v2'

def test_retest_attaches_to_merged(segment):
    s=next(r for r in segment['selected_results'] if r['primary_id']=='00001-V1')
    assert s['id']=='00001-R1' and s['code']=='RETEST_SELECTED'

def test_original_segments_preserved(segment):
    assert len([r for r in segment['records'] if r['kind']=='SEGMENT'])==2
    assert segment['balance']['input']==segment['balance']['accepted']==46
    assert segment['balance']['row_balanced']
    assert len(segment['segment_evidence'])==2

def test_missing_continuation_blocks(segment):
    rows=[r for r in segment['records'] if r['id']!='00001-V1-B']
    merged,conclusions,issues=adjudicate(rows,segment['context'])
    assert not merged and issues[0]['code']=='SEGMENT_INCOMPLETE'

def test_missing_segment_keeps_blocking():
    text='\n'.join(l for l in SEGMENT_CSV.splitlines() if not l.startswith('00001-V1-B'))+'\n'
    s=evaluate({'csv_text':text})
    assert any(i['code']=='SEGMENT_INCOMPLETE' for i in s['segment_issues'])
    assert s['balance']['status']=='待处理'
    assert not any(d['subject']=='00001' and d['visit']=='V1' for d in s['deviations'])
    assert s['balance']['blocked']==2

def test_continuation_reference_invalid(segment):
    rows=segments_of(segment);rows[1]['parent']='NOPE'
    _,_,issues=adjudicate(rows,segment['context'])
    assert {i['code'] for i in issues}=={'SEGMENT_REFERENCE','SEGMENT_INCOMPLETE'}

def test_segment_order_blocks(segment):
    rows=segments_of(segment);rows[1]['at']='2026-10-08T08:00:00+08:00'
    _,_,issues=adjudicate(rows,segment['context'])
    assert issues[0]['code']=='SEGMENT_ORDER'

def test_segment_conflict_blocks(segment):
    rows=segments_of(segment);rows.append(dict(rows[1],id='00001-V1-C'))
    _,_,issues=adjudicate(rows,segment['context'])
    assert any(i['code']=='SEGMENT_CONFLICT' for i in issues)

def test_first_segment_before_window(segment):
    rows=segments_of(segment);rows[0]['at']='2026-10-05T08:00:00+08:00'
    merged,conclusions,issues=adjudicate(rows,segment['context'])
    assert not issues and merged[0]['code_override']=='EARLY'
    assert calculate(merged[0],segment['context'])['code']=='EARLY'
    assert '首段早于采用方案窗始' in conclusions[0]['detail']

def test_version_fallback_keeps_formal_conclusion(segment):
    context=deepcopy(segment['context'])
    context['assignments']['00002']=[{'version':'v9','start':'2026-01-01T00:00:00+08:00','end':'2027-01-01T00:00:00+08:00'}]
    rows=[{'id':'S1','subject':'00002','visit':'V1','at':'2026-10-08T08:00:00+08:00','enrolled':'2026-10-01T00:00:00+08:00','kind':'SEGMENT','parent':'','value':'1.2','unit':'g/L','protocol':'auto','revision':1,'selected_protocol':'v1','value_mg_dl':'120.0','_line':2},
          {'id':'S1-B','subject':'00002','visit':'V1','at':'2026-10-09T08:00:00+08:00','enrolled':'2026-10-01T00:00:00+08:00','kind':'SEGMENT','parent':'S1','value':'1.2','unit':'g/L','protocol':'auto','revision':1,'selected_protocol':'v9','value_mg_dl':'120.0','_line':3}]
    merged,conclusions,issues=adjudicate(rows,context)
    assert not issues and len(merged)==1
    assert merged[0]['selected_protocol']=='v1'
    assert conclusions[0]['adopted_protocol']=='v1'
    assert conclusions[0]['version_fallback']=='是' and conclusions[0]['status']=='版本回退'

def test_seal_covers_segment_conclusion(segment):
    s=deepcopy(segment);s['segment_conclusions'][0]['adopted_protocol']='v1'
    assert freeze(s)['seal']!=segment['archive']['seal']

def test_rerun_same_segment_no_duplicate(tmp_path,monkeypatch):
    c=client(tmp_path,monkeypatch)
    a=c.post('/api/runs',json={'dataset':'segment'}).json()
    b=c.post('/api/runs',json={'dataset':'segment'}).json()
    assert a['manifest']['run_id']==b['manifest']['run_id']
    assert len([r for r in c.get('/api/runs').json() if r['id']==a['manifest']['run_id']])==1
    assert a['balance']['expected']==40 and a['balance']['completed']==40
    r=c.post('/api/runs/'+a['manifest']['run_id']+'/rerun')
    assert r.status_code==200 and r.json()['manifest']['run_id']==a['manifest']['run_id']

def test_upstream_correction_recomputes(tmp_path,monkeypatch):
    c=client(tmp_path,monkeypatch)
    a=c.post('/api/runs',json={'csv_text':BROKEN}).json()
    assert a['balance']['status']=='待处理'
    assert any(i['code']=='SEGMENT_INCOMPLETE' for i in a['segment_issues'])
    b=c.post('/api/runs',json={'csv_text':SEGMENT_CSV}).json()
    assert b['balance']['status']=='可锁库'
    assert a['manifest']['run_id']!=b['manifest']['run_id']
    old=c.get('/api/runs/'+a['manifest']['run_id']).json()
    assert old['balance']['status']=='待处理'

def test_failed_replacement_keeps_old_run(tmp_path,monkeypatch):
    c=client(tmp_path,monkeypatch)
    good=c.post('/api/runs',json={'dataset':'segment'}).json()
    rid=good['manifest']['run_id']
    assert c.post('/api/runs',json={'csv_text':'broken'}).status_code==422
    old=c.get('/api/runs/'+rid)
    assert old.status_code==200 and old.json()['balance']['status']=='可锁库'

def test_segment_page_shows_conclusion(tmp_path,monkeypatch):
    c=client(tmp_path,monkeypatch)
    run=c.post('/api/runs',json={'dataset':'segment'}).json()
    html=c.get('/segment?run_id='+run['manifest']['run_id']).text
    assert '采用日期' in html and '2026-10-10' in html and '采用方案' in html and '阻断原因' in html
