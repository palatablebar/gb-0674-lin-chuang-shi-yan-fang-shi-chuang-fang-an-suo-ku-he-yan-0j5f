from collections import defaultdict
from datetime import timezone, timedelta
from app.coerce import instant
from app.errors import BusinessError
from app.modules.protocol.rules import choose_protocol

ZONE = timezone(timedelta(hours=8))

def day_of(row):
    return (instant(row['at']).astimezone(ZONE).date()-instant(row['enrolled']).astimezone(ZONE).date()).days

def adjudicate(records, context):
    """把同一次计划访视的两段记录裁成唯一可锁库结论。

    返回 (merged, conclusions, issues)：
    - merged：合并后的逻辑访视（kind=PRIMARY，编号沿用首段），供排窗、偏离、复检、冻结共用；
    - conclusions：每组分段的结论（采用日期、采用方案、是否版本回退）；
    - issues：阻断项（缺段、引用无效、顺序颠倒、多段冲突）。
    生效日期取次段（补完）时刻，方案版本按生效日期定版；版本替换失败保留首段版本。
    """
    segments=[r for r in records if r['kind']=='SEGMENT']
    firsts={r['id']:r for r in segments if not r['parent'].strip()}
    children=defaultdict(list);issues=[];merged=[];conclusions=[]
    for cont in segments:
        if not cont['parent'].strip(): continue
        first=firsts.get(cont['parent'])
        if first is None or any(first[k]!=cont[k] for k in ('subject','visit')):
            issues.append({'id':cont['id'],'subject':cont['subject'],'visit':cont['visit'],
                'code':'SEGMENT_REFERENCE','detail':'次段引用的首段不存在，或受试者/访视不一致'})
            continue
        children[cont['parent']].append(cont)
    for fid in sorted(firsts):
        first=firsts[fid];group=children.get(fid,[])
        base={'id':fid,'subject':first['subject'],'visit':first['visit']}
        if not group:
            issues.append({**base,'code':'SEGMENT_INCOMPLETE','detail':'缺少次段依据，访视未补完，继续阻断'});continue
        if len(group)>1:
            issues.append({**base,'code':'SEGMENT_CONFLICT','detail':'同一首段存在多段次段，无法唯一裁决'});continue
        cont=group[0]
        if instant(cont['at'])<=instant(first['at']):
            issues.append({**base,'code':'SEGMENT_ORDER','detail':'次段时刻必须晚于首段'});continue
        fallback=False;note=''
        try:
            adopted=choose_protocol(first['subject'],instant(cont['at']),context)
            if first['visit'] not in context['plans'][adopted]: raise BusinessError('UNKNOWN_VISIT','访视编号不存在')
        except BusinessError as e:
            adopted=first['selected_protocol'];fallback=True;note=f"版本替换失败（{e.message}），保留首段正式结论"
        start,end=context['plans'][adopted][first['visit']]
        row={'id':fid,'subject':first['subject'],'visit':first['visit'],'at':cont['at'],'enrolled':first['enrolled'],
            'kind':'PRIMARY','parent':'','value':first['value'],'unit':first['unit'],'protocol':'auto',
            'revision':max(first['revision'],cont['revision']),'selected_protocol':adopted,
            'value_mg_dl':first['value_mg_dl'],'_line':first['_line'],'merged':True,'segments':[fid,cont['id']]}
        if day_of(first)<start:
            row['code_override']='EARLY';note=(note+'；' if note else '')+'首段早于采用方案窗始'
        merged.append(row)
        conclusions.append({'subject':first['subject'],'visit':first['visit'],
            'adopted_date':instant(cont['at']).astimezone(ZONE).date().isoformat(),'adopted_protocol':adopted,
            'status':'版本回退' if fallback else '已裁决','version_fallback':'是' if fallback else '否',
            'first_id':fid,'first_at':first['at'],'first_protocol':first['selected_protocol'],
            'continuation_id':cont['id'],'continuation_at':cont['at'],'continuation_protocol':cont['selected_protocol'],
            'detail':note or '两段齐备，按补完时刻定版'})
    return merged,conclusions,issues

def apply(state):
    merged,conclusions,issues=adjudicate(state['records'],state['context'])
    state.update(merged_visits=merged,segment_conclusions=conclusions,segment_issues=issues)
    state['segment_evidence']=[{'id':r['id'],'subject':r['subject'],'visit':r['visit'],'at':r['at'],
        'parent':r['parent'],'selected_protocol':r['selected_protocol'],'value_mg_dl':r['value_mg_dl'],'line':r['_line']}
        for r in state['records'] if r['kind']=='SEGMENT']
    state['views']['segment']={'title':'分段裁决','rows':conclusions,
        'metrics':{'分段记录':len(state['segment_evidence']),'已裁决':len(merged),'阻断':len(issues)}}
