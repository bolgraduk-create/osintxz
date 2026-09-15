"""Run the central Registry Backend process.

Production should place this ASGI service behind an HTTPS reverse proxy/load
balancer.  End-user desktop installations do not run this process.
"""
from app.registry_backend.__main__ import main


if __name__ == "__main__":
    main()
