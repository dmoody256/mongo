if [ "Windows_NT" = "$OS" ]; then
  python='/cygdrive/c/python/python37/python.exe'
else
  if [ -f /opt/mongodbtoolchain/v3/bin/python3 ]; then
    python="/opt/mongodbtoolchain/v3/bin/python3"
  else
    python=`which python3`
  fi
fi
