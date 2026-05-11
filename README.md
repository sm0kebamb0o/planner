# Planner Language Interpreter

Интерпретатор языка Плэннер, реализованный на Python. Включает лексер, LL-парсер, вычислитель с поддержкой возвратов и графический IDE на Tkinter.

## Структура проекта

```
src/
  lexer/           Лексический анализ: разбивает исходный текст на токены
  parser/          Синтаксический анализ: строит AST из токенов с помощю L-графа
  interpreter/     Вычислитель: обходит AST, поддерживает возвраты (backtracking)
  gui/             Графический IDE (Tkinter)
  test/            Сквозные (end-to-end) тесты пайплайна
examples/          Примеры программ (.pl, .plan)
```

## Запуск тестов

Все тесты из корня проекта:

```bash
python -m pytest
```

Запуск конкретного модуля:

```bash
python -m pytest src/lexer/test/test_lexer.py -v
python -m pytest src/parser/test/test_reader.py -v
python -m pytest src/interpreter/test/test_interpreter.py -v
python -m pytest src/interpreter/test/test_backtracking.py -v
python -m pytest src/test/test_pipeline.py -v
```

## Описание тестовых модулей

| Модуль | Что проверяет |
|--------|---------------|
| `src/lexer/test/test_lexer.py` | Лексический анализ: атомы, скобки, ссылки на переменные (`.X`, `*X`, `:X`, `!.X`), группировка форм, позиции строк/столбцов, ошибки |
| `src/parser/test/test_reader.py` | Построение AST: атомы, числа, переменные, L-списки, вызовы функций `[]` и `<>`, пустые сопоставители, сериализация в proto |
| `src/interpreter/test/test_interpreter.py` | Вычислитель: арифметика, списки, предикаты, переменные, условия `COND`, пользовательские функции `DEFINE`/`LAMBDA`, циклы, сегментированные вызовы, ошибки выполнения |
| `src/interpreter/test/test_backtracking.py` | Механизм возвратов: оператор `IS` и сопоставление с образцом, сопоставители (`NUM`, `ATOM`, `LIST`, `GT`, `ONE-OF`, `KAPPA`, …), `GATE`/`FAIL`/`AMONG`/`ALT`/`FIND`/`IF`, `PERM`/`STRG`/`TEMP` |
| `src/test/test_pipeline.py` | Сквозные тесты: смок тесты примеров из `examples/`, корректность арифметики, операций над списками, рекурсии (факториал, Фибоначчи, НОД), поиска с возвратами (SUM, 8 ферзей) |

## Запуск графического IDE

```bash
python main.py
```

IDE предоставляет редактор с подсветкой синтаксиса, кнопку запуска (F5) и вывод результатов.
