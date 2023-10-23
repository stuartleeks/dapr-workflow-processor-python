# npm install -g typescript

echo "" >> $HOME/.bashrc
echo 'source <(just --completions bash)' >> $HOME/.bashrc
echo "" >> $HOME/.bashrc

pip install -r src/processor/requirements.txt
pip install -r src/workflow1/requirements.txt
