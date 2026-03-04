import json
with open('results_gold_standard.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print('=== OE ERRORS (FN) ===')
for e in data['errors']['oe']:
    eid = e['id']
    spec = e['specialty']
    etype = e['type']
    htxt = e.get('human_text', '')[:120]
    print(f'  #{eid} [{spec}] {etype}: {htxt}')

print()
print('=== RD ERRORS ===')
for e in data['errors']['rd']:
    eid = e['id']
    spec = e['specialty']
    nlp_r = e['nlp_region']
    human_r = e['human_region']
    human_c = e['human_country']
    aff = e['affiliation']
    print(f'  #{eid} [{spec}] nlp={nlp_r!r} human={human_r!r} country={human_c!r}')
    print(f'    aff: {aff}')

print()
print('=== PE TOP ERRORS (by abs error) ===')  
pe_errs = [e for e in data['errors']['pe'] if e.get('error')]
pe_errs.sort(key=lambda x: x['error'], reverse=True)
for e in pe_errs[:15]:
    eid = e['id']
    spec = e['specialty']
    nlp = e['nlp']
    human = e['human']
    err = e['error']
    notes = e.get('notes', '')[:80]
    print(f'  #{eid} [{spec}] nlp={nlp} human={human} err={err}')
    if notes:
        print(f'    notes: {notes}')
