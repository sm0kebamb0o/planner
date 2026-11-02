from __future__ import annotations

from src.interpreter.database import property_list
from src.interpreter.functions import codec
from src.interpreter.functions.utils import check_arity


def _dump(args, interp):
    check_arity("DUMP", args, 0)
    entries = [interp.database.get(record_id) for record_id in interp.database.ids()]
    entries.sort(key=lambda entry: len(entry.value.elements))
    for entry in entries:
        print(codec.repr_value(entry.value, interp._float_digits),
              codec.repr_value(property_list(entry.properties), interp._float_digits))
    return len(entries)

