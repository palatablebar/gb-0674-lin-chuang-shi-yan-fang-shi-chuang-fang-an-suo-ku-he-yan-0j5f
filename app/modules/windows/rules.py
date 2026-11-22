from datetime import timezone,timedelta
from app.coerce import instant

def calculate(row,context):
    zone=timezone(timedelta(hours=8));day=(instant(row['at']).astimezone(zone).date()-instant(row['enrolled']).astimezone(zone).date()).days
    start,end=context['plans'][row['selected_protocol']][row['visit']]
    code=row.get('code_override') or ('IN_WINDOW' if start<=day<end else ('EARLY' if day<start else 'LATE'))
    return {'id':row['id'],'subject':row['subject'],'visit':row['visit'],'kind':row['kind'],'day':day,'start_day':start,'end_day':end,'selected_protocol':row['selected_protocol'],'code':code,'line':row['_line']}

def apply(state):
    rows=list(state['records'])+list(state.get('merged_visits',[]))
    state['windows']=[calculate(r,state['context']) for r in rows]
    primary=[r for r in state['windows'] if r['kind']=='PRIMARY']
    state['views']['windows']={'title':'访视窗口','rows':state['windows'],'metrics':{'首次访视':len(primary),'窗内':sum(r['code']=='IN_WINDOW' for r in primary),'窗外':sum(r['code']!='IN_WINDOW' for r in primary)}}
