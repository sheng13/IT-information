import sys
sys.path.insert(0, '.')
import app

def test_scrapling_sources_placeholder():
    # 確認重要新聞、品牌和 Release 來源都仍存在於集中清單。
    names = {name for name, _ in app.SOURCES}
    assert 'LWN.net' in names
    assert 'InfoQ' in names
    assert 'Python CPython Releases' in names
    assert 'Kubernetes Releases' in names
    assert 'Google DeepMind AI' in names
    assert 'Dell Tech Blog' in names
    assert 'Lenovo News' in names
    assert 'Lenovo Press' in names
    assert 'Apple Newsroom' in names
    assert 'Apple Machine Learning' in names
    assert 'Samsung Newsroom' in names
    assert 'Samsung Semiconductor' in names
    assert 'Xiaomi Blog' in names
    assert 'Rust Releases' in names
    assert 'Prometheus Releases' in names
    assert 'Ollama Releases' in names
    assert 'LangChain Releases' in names
    assert 'LlamaIndex Releases' in names
    assert 'AutoGen Releases' in names
    assert 'CrewAI Releases' in names
    assert 'MCP Python Releases' in names
    assert 'OpenHands Releases' in names
    assert 'Browser Use Releases' in names
    assert 'Dify Releases' in names
