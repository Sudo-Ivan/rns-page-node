#!/usr/bin/env bash
set -e
cd "$(dirname "${BASH_SOURCE[0]}")"

# Remove previous test artifacts
rm -rf config node-config pages files node.log

# Create directories for config, node identity, pages, and files
mkdir -p config node-config pages files

# Create a sample page and a test file
cat > pages/index.mu << EOF
>Test Page
This is a test page.
EOF

cat > files/text.txt << EOF
This is a test file.
EOF

# Start the page node in the background
python3 ../rns_page_node/main.py -c config -i node-config -p pages -f files > node.log 2>&1 &
NODE_PID=$!

# Wait for node to generate its identity file
echo "Waiting for node identity..."
for i in {1..40}; do
  if [ -f node-config/identity ]; then
    echo "Identity file found"
    break
  fi
  sleep 0.25
done
if [ ! -f node-config/identity ]; then
  echo "Error: node identity file not found" >&2
  kill $NODE_PID
  exit 1
fi

# Run the client test
python3 test_client.py

# Clean up
kill $NODE_PID 