# Tyrant Development Guidelines

## Build & Configuration

### Python Environment
Always use the virtual environment in .venv/

```bash
pip install -r requirements.txt
```

### Configuration
Create a `.env` file in the project root:
```env
MISTRAL_API_KEY=your_api_key_here
```

## Testing

### Running Tests
The project uses Python's built-in `unittest` framework (no pytest):
```bash
python -m unittest tests.test_main -v
```

### Adding New Tests
1. Add test methods to `tests/test_main.py` or create new test files in `tests/`
2. Test files must follow the pattern `test_*.py`
3. Import the source module by adding `src` to path:
   ```python
   import sys, os
   sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
   ```
4. Use `unittest.mock` for mocking external dependencies (Mistral API, sounddevice, keyboard, subprocess)

### Test Example
```python
@patch('main.subprocess.run')
def test_type_text(self, mock_run):
    main.type_text("hello")
    mock_run.assert_called_with(['xdotool', 'type', '--clearmodifiers', 'hello'])
```

## Code Style

- Standard Python conventions (PEP 8)
- Use `logging` module for output (not print)
- External API calls and system interactions should be mockable for testing
- Threading is used for PTT mode and tray icon management
