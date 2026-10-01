"""Generated gRPC stubs land in this package.

`scripts/gen_contracts.py` runs `grpcio-tools` over `shared/contracts/proto/` and
writes `*_pb2.py` / `*_pb2_grpc.py` here. Those generated files are git-ignored.

Services import them defensively (try/except) so the REST path still boots even
before code generation has been run — see each service's `app/api/grpc_server.py`.
"""
