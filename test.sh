#! /bin/sh

echo "Fibonacci Numbers"
echo "-----------------"
cat ./tests/fib.pi | python3 jpi.py

echo "\n\nSquare Numbers  "
echo "-----------------"
cat ./tests/sq.pi | python3 jpi.py

echo "\n\nArithmatic = 21  "
echo "-----------------"
cat ./tests/arith.pi | python3 jpi.py
