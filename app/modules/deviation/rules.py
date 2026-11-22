from collections import defaultdict

def detect(windows,context,segment_keys=None):
    segment_keys=segment_keys or set()
    primary=defaultdict(list)
    for row in windows:
        if row['kind']=='PRIMARY':primary[(row['subject'],row['visit'])].append(row)
    issues=[];completed=[]
    for subject in sorted(context['subjects']):
        for visit in context['required_visits']:
            if (subject,visit) in segment_keys:continue
            items=primary.get((subject,visit),[])
            if not items:issues.append({'subject':subject,'visit':visit,'id':'','code':'MISSING_PRIMARY'});continue
            if len(items)>1:issues.append({'subject':subject,'visit':visit,'id':','.join(r['id'] for r in items),'code':'DUPLICATE_PRIMARY'});continue
            row=items[0]
            if row['code']!='IN_WINDOW':issues.append({**row,'code':'WINDOW_'+row['code']})
            else:completed.append(row)
    return issues,completed

def apply(state):
    merged_keys={(m['subject'],m['visit']) for m in state.get('merged_visits',[])}
    suppressed={(i['subject'],i['visit']) for i in state.get('segment_issues',[])}-merged_keys
    issues,completed=detect(state['windows'],state['context'],suppressed);state.update(deviations=issues,completed=completed)
    state['views']['deviation']={'title':'偏离复核','rows':issues,'metrics':{'完成访视':len(completed),'缺失或偏离':len(issues),'缺首次访视':sum(x['code']=='MISSING_PRIMARY' for x in issues)}}
