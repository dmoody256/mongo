#!/bin/sh
export NVM_DIR="$HOME/.nvm"
if [ -s "$NVM_DIR/nvm.sh" ]
then
    \. "$NVM_DIR/nvm.sh"
else
    curl -o- https://raw.githubusercontent.com/creationix/nvm/v0.34.0/install.sh | sh
    \. "$NVM_DIR/nvm.sh"
fi
nvm install 12
if [ "$1" = "install" ]
then
    npm install
fi

if [ "$1" = "start" ]
then
    npm start
fi

if [ "$1" = "build" ]
then
    npm run build
fi