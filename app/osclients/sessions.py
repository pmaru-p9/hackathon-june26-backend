"""Build auth kwargs for openstacksdk Connection. Source = user token, dest = svc acct."""


def source_auth_kwargs(auth_url: str, token: str, project_id: str) -> dict:
    return {"auth_type": "v3token", "auth_url": auth_url, "token": token,
            "project_id": project_id}


def dest_auth_kwargs(auth_url: str, username: str, password: str, project_name: str,
                     user_domain: str, project_domain: str) -> dict:
    return {"auth_type": "v3password", "auth_url": auth_url, "username": username,
            "password": password, "project_name": project_name,
            "user_domain_name": user_domain, "project_domain_name": project_domain}
