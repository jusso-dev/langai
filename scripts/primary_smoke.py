"""Complete real multilingual-model verification against the running API."""

import sys
from integration_smoke import main

if __name__ == "__main__":
    main(["--base-model", "auto", *sys.argv[1:]])
