---
tags:
  - laravel
  - pattern
---
# Laravel Service Pattern

Services hold business logic. Controllers call services. Services call repositories.
Use DB::transaction for multi-step writes. Return typed models from service methods.
