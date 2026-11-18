import json
from unittest.mock import Mock
import pytest
from backend.ai.analyzer import AnalyzerError
from backend.ai.extra_modes import interview_mode, contribution_mode
M={'full_name':'a/b'}
R=[{'path':'src/a.py','content':'print(1)'}]
def test_interview_evidence_validation():
    c=Mock();c.models.generate_content.return_value.text=json.dumps({'questions':[{'question':'Explain entry point','answer':'Main','evidence_paths':['src/a.py'],'verification_note':'limited'}]*5})
    assert len(interview_mode(M,R,client=c)['questions'])==5
    c.models.generate_content.return_value.text=json.dumps({'questions':[{'question':'Explain entry','answer':'A','evidence_paths':['fake.py'],'verification_note':'limited'}]*5})
    with pytest.raises(AnalyzerError):interview_mode(M,R,client=c)
def test_contribution_evidence_validation():
    c=Mock();x={'task':'Improve docs','why_beginner_friendly':'small','evidence_paths':['src/a.py'],'investigation_plan':['read'], 'risks':['unknown'], 'unverified':'Not an open issue'}
    c.models.generate_content.return_value.text=json.dumps(x)
    assert contribution_mode(M,R,client=c)['task']=='Improve docs'
    x['evidence_paths']=['notthere']
    c.models.generate_content.return_value.text=json.dumps(x)
    with pytest.raises(AnalyzerError):contribution_mode(M,R,client=c)
