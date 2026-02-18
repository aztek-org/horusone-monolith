---
description: Review Python code for best practices and potential issues
agent: python-expert
subtask: true
---

Review the Python file $ARGUMENTS for:

**Code Quality:**
- PEP 8 compliance and code style
- Proper naming conventions (snake_case for functions/variables, PascalCase for classes)
- Line length and formatting

**Type Safety:**
- Type hint usage and completeness
- Mypy compatibility
- Generic types where appropriate

**Code Correctness:**
- Potential bugs and edge cases
- Logic errors
- Missing error handling

**Performance:**
- Inefficient algorithms or data structures
- Unnecessary computations
- Blocking operations in async code

**Testing:**
- Test coverage
- Missing test cases
- Testability of the code

**Security:**
- Input validation
- SQL injection vulnerabilities
- Sensitive data handling

**Best Practices:**
- Modern Python features (3.10+)
- Proper use of context managers
- Async/await patterns
- Logging instead of print statements

Provide specific suggestions with code examples showing the improvements.
