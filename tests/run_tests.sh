#!/usr/bin/env bash
set -e
cd "$(dirname "${BASH_SOURCE[0]}")"

# Remove previous test artifacts
rm -rf config node-config pages files node.log

# Create directories for config, node identity, pages, and files
mkdir -p config node-config pages files

# Create a sample page and a test file
cat > pages/index.mu << 'EOF'
#!/usr/bin/env python3
import os

print("`F0f0`_`Test Page`_")
print("This is a test page with environment variable support.")
print()

print("`F0f0`_`Environment Variables`_")
params = []
for key, value in os.environ.items():
    if key.startswith(('field_', 'var_')):
        params.append(f"- `Faaa`{key}`f: `F0f0`{value}`f")

if params:
    print("\n".join(params))
else:
    print("- No parameters received")

print()
print("`F0f0`_`Remote Identity`_")
remote_id = os.environ.get('remote_identity', '33aff86b736acd47dca07e84630fd192')  # Mock for testing
print(f"`Faaa`{remote_id}`f")
EOF

chmod +x pages/index.mu

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