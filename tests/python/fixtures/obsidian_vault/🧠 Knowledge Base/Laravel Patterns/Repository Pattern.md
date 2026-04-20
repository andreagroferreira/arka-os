---
tags:
  - laravel
  - pattern
---
# Repository Pattern

Repositories abstract data access. Model queries live inside repositories, not controllers.
Services depend on repository interfaces, enabling swap-in of test doubles.
