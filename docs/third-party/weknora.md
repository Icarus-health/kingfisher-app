# WeKnora rank fusion reference

The small reciprocal rank fusion routine in `sidecar/icarus_memory/knowledge_search.py`
is adapted from the algorithm in Tencent WeKnora's `fuseRankings`:

https://github.com/Tencent/WeKnora/blob/5c5d46d9fb556a7efa19d1a23331f4ce83ac2031/internal/application/service/memory/vector.go

Source inspected on 2026-09-19. The implementation is translated to Python, removes
duplicate votes within one channel, and keeps deterministic lexical-first ties.
The k=60 fusion and initial cosine floor 0.5 follow that reference; the latter is
an experimental starting point, not a qualified German relevance threshold.
Kingfisher's canonical evidence, source-generation checks and snapshot handling
are its own implementation. No WeKnora services, model assets or dependencies
are bundled. The complete upstream repository contains separately licensed third-party
components; this notice applies to the small referenced algorithm only.

Upstream MIT notice (from its LICENSE at the pinned commit):

Copyright (C) 2025 Tencent. All rights reserved.

Permission is hereby granted, free of charge, to any person obtaining a copy of
this software and associated documentation files (the "Software"), to deal in
the Software without restriction, including without limitation the rights to
use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies
of the Software, and to permit persons to whom the Software is furnished to
do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
