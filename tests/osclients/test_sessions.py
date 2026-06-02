from app.osclients.sessions import source_auth_kwargs, dest_auth_kwargs

def test_source_uses_token():
    kw = source_auth_kwargs(auth_url="http://src/v3", token="TKN", project_id="p1")
    assert kw["auth_type"] == "v3token"
    assert kw["token"] == "TKN" and kw["project_id"] == "p1"

def test_dest_uses_password_scoped_to_target_project():
    kw = dest_auth_kwargs(auth_url="http://dst/v3", username="svc", password="pw",
                          project_name="target", user_domain="Default",
                          project_domain="Default")
    assert kw["auth_type"] == "v3password"
    assert kw["project_name"] == "target"
    assert kw["username"] == "svc"
