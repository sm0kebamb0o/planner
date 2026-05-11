import sys
from ...common.proto import common_pb2
sys.modules.setdefault("common_pb2", common_pb2)
from . import graph_pb2
