from unittest.mock import Mock
import pytest
from backend.rag.chunker import chunk_files
from backend.rag.rag_store import collection_name,store_chunks,query_chunks,StoreError
from backend.rag.embeddings import embed_texts,EmbeddingError
from backend.rag.retriever import retrieve
from backend.ai.qa import answer_question,QAError

def test_chunks_preserve_lines_and_are_idempotent():
    records=[{'path':'src/a.py','content':'a\nb\nc\nd\ne\nf\n'}]
    chunks=chunk_files(records,'me/repo','123',size=6,overlap=2)
    assert chunks and chunks==chunk_files(records,'me/repo','123',size=6,overlap=2)
    for c in chunks:
        assert c['text']==''.join(records[0]['content'].splitlines(keepends=True)[c['start_line']-1:c['end_line']])
    assert len({c['id'] for c in chunks})==len(chunks)

def test_chunk_rejects_invalid_settings():
    with pytest.raises(ValueError):chunk_files([], 'r','rev',5,5)

def test_revision_collection_isolation():
    assert collection_name('a/b','v1','model') != collection_name('a/b','v2','model')
    assert collection_name('a/b','v1','model') != collection_name('a/c','v1','model')

def test_upsert_is_repeatable():
    collection=Mock()
    client=Mock()
    client.get_or_create_collection.return_value=collection
    chunks=chunk_files([{'path':'a.py','content':'hello\n'}],'a/b','r')
    for _ in range(2):
        assert store_chunks('a/b','r','embed',chunks,[[.5,.2]],client=client)==1
    assert collection.upsert.call_count==2
    assert collection.upsert.call_args.kwargs['metadatas'][0]['path']=='a.py'

def test_retrieval_correct_repo_and_query():
    calls=[]
    def fake_query(*args,**kwargs):calls.append((args,kwargs));return [{'path':'f.py','text':'x'}]
    result=retrieve('a/b','commit','where?', top_k=3,embedder=lambda x,task_type:[[.1,.2]],query_fn=fake_query)
    assert result[0]['path']=='f.py' and calls[0][0][0:2]==('a/b','commit') and calls[0][1]['top_k']==15

def test_retrieval_prevents_one_readme_from_crowding_out_source():
    candidates=[{'path':'README.md','text':str(i)} for i in range(8)]
    candidates += [{'path':'lib/core/Axios.js','text':str(i)} for i in range(3)]
    candidates += [{'path':'lib/core/dispatchRequest.js','text':'dispatch'}]
    result=retrieve('a/b','revision','interceptors?',top_k=5,embedder=lambda *a,**kw:[[1.,2.]],
        query_fn=lambda *a,**kw:candidates)
    assert len(result)==5
    assert [c['path'] for c in result]==['README.md','README.md','lib/core/Axios.js','lib/core/Axios.js','lib/core/dispatchRequest.js']

def test_retrieval_fills_requested_window_when_only_one_file_exists():
    candidates=[{'path':'only.py','text':str(i)} for i in range(8)]
    result=retrieve('a/b','revision','where?',top_k=5,embedder=lambda *a,**kw:[[1.,2.]],
        query_fn=lambda *a,**kw:candidates)
    assert result==candidates[:5]

def test_missing_question_and_no_evidence():
    with pytest.raises(ValueError):retrieve('a/b','rev',' ')
    assert answer_question('anything?',[])['uncertain']

def test_qa_validation_rejects_fake_citation():
    client=Mock()
    client.models.generate_content.return_value.text='{"answer":"x","uncertain":false,"citations":[{"path":"fake.py","start_line":1,"end_line":2}]}'
    with pytest.raises(QAError):answer_question('where?', [{'path':'real.py','start_line':5,'end_line':10,'text':'code'}],client=client)

def test_qa_accepts_grounded_citation():
    client=Mock()
    client.models.generate_content.return_value.text='{"answer":"found","uncertain":false,"citations":[{"path":"real.py","start_line":5,"end_line":6}]}'
    assert answer_question('where?', [{'path':'real.py','start_line':5,'end_line':10,'text':'code'}],client=client)['answer']=='found'

def test_qa_cites_complete_supplied_passage_and_deduplicates():
    client=Mock()
    client.models.generate_content.return_value.text='{"answer":"The two branches are shown in the supplied passage.","uncertain":false,"citations":[{"path":"a.py","start_line":11,"end_line":12},{"path":"a.py","start_line":13,"end_line":14}]}'
    result=answer_question('where?', [{'path':'a.py','start_line':10,'end_line':15,'text':'first\nsecond\nthird\nfourth\nfifth\nsixth\n'}],client=client)
    assert result['citations']==[{'path':'a.py','start_line':10,'end_line':15}]

def test_embedding_client_mock():
    client=Mock();client.models.embed_content.return_value.embeddings=[Mock(values=[1.,2.])]
    assert embed_texts(['hello'],client=client)==[[1.,2.]]
    with pytest.raises(EmbeddingError):embed_texts(['hello','world'],client=client)

def test_embedding_two_keeps_inputs_separate_and_uses_query_instruction():
    client=Mock()
    def embed(**kwargs):
        assert 'config' not in kwargs
        assert all(isinstance(c,dict) and len(c['parts'])==1 for c in kwargs['contents'])
        return Mock(embeddings=[Mock(values=[float(i),1.]) for i,_ in enumerate(kwargs['contents'])])
    client.models.embed_content.side_effect=embed
    assert len(embed_texts(['one','two'],client=client,model='gemini-embedding-2'))==2
    embed_texts(['where?'],client=client,model='gemini-embedding-2',task_type='RETRIEVAL_QUERY')
    assert client.models.embed_content.call_args.kwargs['contents'][0]['parts'][0]['text']=='task: code retrieval | query: where?'

def test_embedding_batches_preserve_all_vectors():
    client=Mock()
    def embed(**kwargs):
        return Mock(embeddings=[Mock(values=[float(c['parts'][0]['text'].split()[-1]),1.]) for c in kwargs['contents']])
    client.models.embed_content.side_effect=embed
    vectors=embed_texts([str(i) for i in range(105)],client=client)
    assert [v[0] for v in vectors]==list(range(105))
    assert client.models.embed_content.call_count==3

def test_index_preserves_deep_source_while_report_stays_bounded(monkeypatch):
    import backend.services.pipeline as pipeline, backend.github.github_client as github_client
    text='# heading\n'*1200+'def load_session():\n    return True\n'
    tree=[{'path':'src/sessions.py','type':'blob','size':len(text)}]
    monkeypatch.setattr(pipeline,'fetch_repo_metadata',lambda *a:{'default_branch':'main'})
    monkeypatch.setattr(pipeline,'fetch_tree',lambda *a:(tree,False))
    monkeypatch.setattr(github_client,'fetch_file_content',lambda *a:text)
    revision='a'*40
    normal=pipeline.collect_repo('https://github.com/o/r',revision=revision)
    indexed=pipeline.collect_repo('https://github.com/o/r',revision=revision,for_index=True)
    assert 'def load_session' not in normal['records'][0]['content']
    assert 'def load_session' in indexed['records'][0]['content']
    chunks=chunk_files(indexed['records'],'o/r',revision)
    assert any('def load_session' in c['text'] and c['start_line']>1 for c in chunks)

def test_embedding_retries_transient_quota_using_server_delay(monkeypatch):
    import backend.rag.embeddings as embeddings
    class RateLimit(Exception):
        code=429
        details={'error':{'details':[{'retryDelay':'3s'}]}}
    waits=[]
    monkeypatch.setattr(embeddings.time,'sleep',waits.append)
    client=Mock()
    client.models.embed_content.side_effect=[RateLimit(),Mock(embeddings=[Mock(values=[1.,2.])])]
    assert embed_texts(['code'],client=client)==[[1.,2.]]
    assert waits==[4.] and client.models.embed_content.call_count==2

@pytest.mark.parametrize('code,delay',[(403,'3s'),(429,'3600s')])
def test_embedding_does_not_retry_permission_or_long_quota(monkeypatch,code,delay):
    import backend.rag.embeddings as embeddings
    error=RuntimeError('provider error')
    error.code=code;error.details={'error':{'details':[{'retryDelay':delay}]}}
    monkeypatch.setattr(embeddings.time,'sleep',lambda _:pytest.fail('must not wait'))
    client=Mock();client.models.embed_content.side_effect=error
    with pytest.raises(EmbeddingError):embed_texts(['code'],client=client)
    assert client.models.embed_content.call_count==1

def test_parallel_index_fetch_preserves_filters_order_and_failure_handling(monkeypatch):
    import backend.github.github_client as github_client
    called=[]
    def fetch(owner,repo,path,revision):
        called.append((path,revision))
        if path=='src/b.py':raise github_client.GitHubError('unavailable')
        if path=='src/c.py':return '-----BEGIN PRIVATE KEY-----'
        return 'def safe():\n    return True\n'
    monkeypatch.setattr(github_client,'fetch_file_content',fetch)
    paths=['src/a.py','.env','src/b.py','src/c.py']
    tree=[{'path':p,'type':'blob','size':100} for p in paths]
    results=github_client.collect_selected_file_contents('o','r','a'*40,
        [(p,1) for p in paths],tree,fetch_workers=4)
    assert [r['path'] for r in results]==paths
    assert '.env' not in {p for p,_ in called}
    assert all(rev=='a'*40 for _,rev in called)
    assert [r['path'] for r in results if not r['skipped']]==['src/a.py']

def test_embedding_checkpoint_resumes_batches_and_rejects_changed_inputs(tmp_path):
    client=Mock();calls=[]
    def first(**kwargs):
        calls.append(kwargs)
        if len(calls)==2:raise RuntimeError('temporary provider stop')
        return Mock(embeddings=[Mock(values=[float(i),1.]) for i in range(50)])
    client.models.embed_content.side_effect=first
    texts=[str(i) for i in range(51)];path=tmp_path/'vectors.json'
    with pytest.raises(EmbeddingError):embed_texts(texts,client=client,checkpoint_path=path)
    retry=Mock();retry.models.embed_content.return_value=Mock(embeddings=[Mock(values=[50.,1.])])
    vectors=embed_texts(texts,client=retry,checkpoint_path=path)
    assert [v[0] for v in vectors]==list(range(51))
    assert len(retry.models.embed_content.call_args.kwargs['contents'])==1
    changed=Mock()
    changed.models.embed_content.side_effect=lambda **kw:Mock(embeddings=[Mock(values=[1.,2.]) for _ in kw['contents']])
    embed_texts(['changed']+texts[1:],client=changed,checkpoint_path=path)
    assert changed.models.embed_content.call_count==2
    assert len(changed.models.embed_content.call_args_list[0].kwargs['contents'])==50

def test_completed_index_resume_requires_matching_settings_count_and_metadata(monkeypatch,tmp_path):
    import backend.services.pipeline as pipeline
    monkeypatch.setattr(pipeline,'CHROMA_PATH',str(tmp_path))
    repo='o/r';revision='a'*40
    result=dict(repository=repo,revision=revision,chunks=2,indexed_files=1,tree_incomplete=False)
    pipeline.record_completed_index(result)
    col=Mock();col.count.return_value=2
    col.get.return_value={'metadatas':[{'repo':repo,'revision':revision,'path':'a.py'}]*2}
    monkeypatch.setattr(pipeline,'get_collection',lambda *a:col)
    monkeypatch.setattr(pipeline,'collect_repo',lambda *a,**kw:pytest.fail('must reuse completed index'))
    assert pipeline.index_repo('https://github.com/o/r',revision=revision,resume=True)['resumed']
    col.metadata = {'repolens_complete': False}
    assert pipeline.resume_completed_index(repo,revision) is None
    col.metadata = {'repolens_complete': True}
    col.count.return_value=1
    assert pipeline.resume_completed_index(repo,revision) is None
    col.count.return_value=2
    monkeypatch.setattr(pipeline,'RAG_CONTEXT_BUDGET',123)
    assert pipeline.resume_completed_index(repo,revision) is None
