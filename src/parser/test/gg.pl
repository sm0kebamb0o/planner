[DEFINE MEMBER (LAMBDA (A L)
    [COND ([EQ .L ()] ())
          ([EQ .A [ELEM 1 .L]] T)
          (T [MEMBER .A [REST 1 .L]])])]


[MEMBER 2 (1 2 3)]