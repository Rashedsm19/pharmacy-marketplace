"""
Adapters for systems outside this application.

Everything in here talks to something the platform does not control — an email
provider, ZATCA's clearance API, the file store — and each one is selected by an
env var with a stub backend as the default, so local development and the test
suite never reach the network. Business logic belongs in the domain services one
level up; these modules only carry a message across the boundary.
"""
