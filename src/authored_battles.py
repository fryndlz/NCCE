"""Expose player-written Sheet battle reports as primary authored documents.

The source text is never rewritten, translated or sent to a provider. Semantic
presentation belongs to the renderer; mechanical evidence stays separate.
"""
def has_report(battle):
    return bool(str(battle.get('notes') or '').strip())


def report(battle, evidence=(), event_ids=()):
    if not has_report(battle):return None
    text=battle['notes']
    scenario=battle.get('scenario') or 'Engagement'
    title=scenario+' — '+battle['territory'] if battle.get('territory') else scenario
    return {'title':title,'document_type':'incident_record','provenance_class':'player_authored',
            'writer_status':'ready','writer_model':None,'authored_text':text,
            'authored_report_revision':1,
            'blocks':[{'type':'body_paragraph','text':text}],
            'evidence':list(evidence),'source_event_ids':list(event_ids),
            'source_ids':['live:campaign-sheet'],'source_label':'Player-authored · campaign Sheet battle report',
            'source_locator':f"Battles!row {battle['source_row']} · Notes" if battle.get('source_row') else 'Battles · Notes',
            'reference':f"NC/BATTLE_REPORT/{battle.get('id') or battle.get('source_battle_key') or 'SOURCE'}",
            'author':'Player-authored campaign record','occurred_at':battle.get('date')}
