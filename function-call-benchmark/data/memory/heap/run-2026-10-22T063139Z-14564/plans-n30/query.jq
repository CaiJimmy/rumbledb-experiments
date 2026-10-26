declare function local:fib($n as integer) as integer {
  if ($n le 1) then $n else local:fib($n - 1) + local:fib($n - 2)
};
local:fib(30)
