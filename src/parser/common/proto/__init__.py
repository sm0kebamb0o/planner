import sys

from . import common_pb2

# Сгенерированные модули графа и грамматики импортируют зависимость по имени из protoc.
sys.modules.setdefault("common_pb2", common_pb2)
