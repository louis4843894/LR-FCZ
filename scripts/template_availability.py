"""Explicit absence is different from a missing field or unmatched template."""
def availability(row,key,kind='list'):
 if not isinstance(row,dict) or key not in row:return 'unknown'
 value=row[key]
 if kind=='list':return 'absent' if isinstance(value,list) and not value else 'present' if isinstance(value,list) else 'unknown'
 return 'absent' if value is None else 'present' if isinstance(value,dict) and value else 'unknown'
