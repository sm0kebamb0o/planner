PROTO_SRC = src/proto/graph.proto
PROTO_OUT = src/proto

proto:
	protoc --python_out=$(PROTO_OUT) --proto_path=$(PROTO_OUT) $(notdir $(PROTO_SRC))

.PHONY: proto
