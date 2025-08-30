from collections import deque

STACK_KEY = "state_stack"

def push_state(user_data, state):
    stack = user_data.get(STACK_KEY)
    if stack is None:
        stack = deque()
        user_data[STACK_KEY] = stack
    stack.append(state)

def pop_state(user_data):
    stack = user_data.get(STACK_KEY)
    if not stack:
        return None
    return stack.pop()

def clear_stack(user_data):
    user_data[STACK_KEY] = deque()
