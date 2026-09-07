from app.osint.username_fusion import UsernameProfileFusionPolicy, UsernameProfileObservation

def obs(provider, confidence=0.9, reliability=0.9, url="https://t.me/example"):
    return UsernameProfileObservation(provider, url, confidence, reliability)

def test_single_provider_below_one():
    f = UsernameProfileFusionPolicy.fuse([obs("Sherlock")])["https://t.me/example"]
    assert f.provider_count == 1
    assert 0.60 <= f.confidence <= 0.86
    assert f.confidence < 1.0

def test_second_provider_increases_confidence():
    one = UsernameProfileFusionPolicy.fuse([obs("Sherlock")])["https://t.me/example"]
    two = UsernameProfileFusionPolicy.fuse([obs("Sherlock"), obs("user_scanner")])["https://t.me/example"]
    assert two.provider_count == 2
    assert two.confidence > one.confidence
    assert two.confidence <= 0.97

def test_same_provider_duplicates_count_once():
    f = UsernameProfileFusionPolicy.fuse([obs("user_scanner",0.8,0.8),obs("user_scanner",0.95,0.95)])["https://t.me/example"]
    assert f.provider_count == 1

def test_different_urls_not_fused():
    fused = UsernameProfileFusionPolicy.fuse([obs("Sherlock"),obs("user_scanner",url="https://www.tiktok.com/@example")])
    assert len(fused) == 2
