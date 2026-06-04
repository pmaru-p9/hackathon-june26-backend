from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    namespace: str = "pcd-region-one"
    cinder_microversion: str = "3.8"
    manageable_poll_seconds: int = 5
    manageable_poll_attempts: int = 12
    verify_active_seconds: int = 5
    verify_active_attempts: int = 60          # up to 5 min for the dest VM to boot


settings = Settings()
