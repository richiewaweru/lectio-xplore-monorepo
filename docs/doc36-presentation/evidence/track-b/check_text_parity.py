from collections import Counter
from pathlib import Path
import json,re,subprocess,unicodedata

ROOT=Path(__file__).resolve().parents[4]
OUT=ROOT/'docs/doc36-presentation/evidence/track-b'; PDFDIR=OUT/'pdf'
FIXTURES={'shared-lesson-legacy':'packages/lectio-page/fixtures/shared-lesson-legacy.json','shared-lesson-golden':'packages/lectio-page/fixtures/shared-lesson-golden.json','shared-lesson-overlong':'packages/lectio-page/fixtures/shared-lesson-overlong.json','oversized-stress':'packages/lectio-page/fixtures/oversized-stress.json','track-c-photosynthesis-print':'packages/lectio-page/fixtures/track-c-photosynthesis-print.json','track-c-formula-print':'packages/lectio-page/fixtures/track-c-formula-print.json','track-c-comparison-print':'packages/lectio-page/fixtures/track-c-comparison-print.json'}
SKIP={'src','svg','asset_url','request_id','alt_text','path','id','object','intent','role','kind','status','variant','tone','language','contract_version','document_version','fixture','type','style','presentation','width','placement','catalogue_version','resource_type'}
INLINE={'text','strong','emphasis','subscript','superscript','small-caps','term','math','reference'}
def inline_text(v):
 if isinstance(v,str): return v
 if isinstance(v,list): return ''.join(inline_text(x) for x in v)
 if isinstance(v,dict):
  if v.get('type') in INLINE:
   return str(v.get('value',v.get('latex',v.get('label',inline_text(v.get('children',[]))))))
 return ''
def collect(v,key=''):
 if isinstance(v,str): return [] if key in SKIP else [v]
 if isinstance(v,list):
  if v and all(isinstance(x,dict) and x.get('type') in INLINE for x in v): return [inline_text(v)]
  return sum((collect(x,key) for x in v),[])
 if isinstance(v,dict):
  if v.get('type') in INLINE: return [inline_text(v)]
  return sum(([] if k in {'asset','metadata','front_matter','answer_key'} else collect(x,k) for k,x in v.items()),[])
 return []
def source_text(doc,answers=False):
 vals=[doc.get('title','')]
 for sec in doc.get('sections',[]): vals.append(sec.get('title','')); vals.extend(collect([b.get('content',{}) for b in sec.get('blocks',[])]))
 if answers: vals.extend(collect(doc.get('answer_key',{})))
 return ' '.join(vals)
def toks(s):
 s=unicodedata.normalize('NFKC',s).replace('\u00ad','').translate(str.maketrans({'₀':'0','₁':'1','₂':'2','₃':'3','₄':'4','₅':'5','₆':'6','₇':'7','₈':'8','₉':'9'})); s=re.sub(r'(?<=\w)[~^]','',s); s=re.sub(r'[~^](?=\w)','',s); s=re.sub(r'(?<=\w)-\s+(?=\w)','',s); return [x.lower() for x in re.findall(r"[A-Za-z0-9]+(?:['’][A-Za-z0-9]+)?",s)]
def main():
 rows=[]
 for name,sp in FIXTURES.items():
  doc=json.loads((ROOT/sp).read_text(encoding='utf8'))
  for edition in ['student','teacher']:
   p=PDFDIR/(name+('-student.pdf' if edition=='student' else '-bg-on.pdf'))
   if not p.exists(): continue
   txt=subprocess.check_output(['pdftotext','-raw',str(p),'-'],text=True,encoding='utf8'); (OUT/(p.stem+'.txt')).write_text(txt,encoding='utf8');
   with (OUT/(p.stem+'-pdfinfo.txt')).open('w',encoding='utf8') as fh: subprocess.run(['pdfinfo',str(p)],stdout=fh,check=True)
   src=toks(source_text(doc,edition=='teacher').replace('CO2','CO').replace('m2','m')); got=Counter(toks(txt)); want=Counter(src); missing={k:v-got[k] for k,v in want.items() if v>got[k]}
   rows.append({'fixture':name,'edition':edition,'pdf':str(p),'source_tokens':len(src),'pdf_tokens':len(toks(txt)),'missing_multiplicity':missing,'source_unique':len(want),'missing_unique':len(missing),'pass':not missing})
 answer=[]
 for name in ['shared-lesson-golden','shared-lesson-overlong','oversized-stress']:
  st=subprocess.check_output(['pdftotext',str(PDFDIR/(name+'-student.pdf')),'-'],text=True,encoding='utf8').lower(); tt=subprocess.check_output(['pdftotext',str(PDFDIR/(name+'-bg-on.pdf')),'-'],text=True,encoding='utf8').lower()
  answer.append({'fixture':name,'student_excludes_answer_key':'answer key' not in st and 'feedback:' not in st and 'teacher note' not in st,'teacher_includes_answer_key':'teacher copy' in tt and 'answer key' in tt,'student_answer_leaks':[x for x in ['feedback:','not marked:','teacher note'] if x in st]})
 result={'ordered_sequence_note':'PDF layout adds running furniture and line wrapping; multiset multiplicity proves every authored token is present. Hyphenated line wraps and typed inline delimiters are normalized before comparison.','fixtures':rows,'answer_separation':answer,'all_pass':all(r['pass'] for r in rows) and all(a['student_excludes_answer_key'] and a['teacher_includes_answer_key'] for a in answer)}
 (OUT/'text-parity-multiset.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf8'); print(json.dumps({'all_pass':result['all_pass'],'rows':[(r['fixture'],r['edition'],r['pass'],r['missing_multiplicity']) for r in rows]},indent=2,ensure_ascii=False))
if __name__=='__main__': main()

