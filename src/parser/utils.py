from uuid import uuid4


class IdGenerator:
    _instance: "IdGenerator | None" = None

    def __new__(cls) -> "IdGenerator":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def next_id(self, class_name: str) -> str:
        return f"{class_name}_{uuid4()}"


class AutoIdMeta(type):
    def __call__(cls, *args, **kwargs):
        if "id" in kwargs:
            next_id = kwargs["id"]
            kwargs.pop("id")
        else:
            next_id = IdGenerator().next_id(cls.__name__)

        instance = super().__call__(*args, **kwargs)
        instance.id = next_id
        return instance
