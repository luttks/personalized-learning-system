import re

raw = '''`json
{
  "nhom_co_ban": {}
}
`
{
  "exam_content": "blah"
}
'''
match = re.search(r'`(?:json)?\s*(\{.*?\})\s*`', raw, re.DOTALL)
if match:
    print('MATCHED:', match.group(1))
else:
    print('NO MATCH')
