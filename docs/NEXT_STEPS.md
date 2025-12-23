# Next Steps for Simplification

## ✅ Completed
- [x] Removed CLI entry point

## 🎯 Next Priority Steps (Keep FastAPI, UI, MCP)

### Priority 1: Add Demo Mode Flag (30 min)
**Why**: Allows toggling between demo and production features without code changes

**Action**:
1. Add `demo_mode` to config schema
2. Add to `config/default.yaml`
3. Use flag to disable personalization in demo mode

**Files to modify**:
- `src/ai_tutor/config/schema.py` - Add demo_mode field
- `config/default.yaml` - Add `demo_mode: true`
- `src/ai_tutor/system.py` - Check flag before initializing personalization

**Impact**: Easy toggle, no code removal needed initially

---

### Priority 2: Simplify/Disable Personalization in Demo Mode (2-3 hours)
**Why**: Personalization adds ~500 lines and complexity, not core to RAG demo

**Action**:
1. When `demo_mode=true`, skip personalization initialization
2. Use static style/difficulty instead of adaptive
3. Keep code but make it optional

**Files to modify**:
- `src/ai_tutor/system.py` - Conditional personalization init
- `src/ai_tutor/system.py` - Use static values in `answer_question()` when demo_mode
- `src/ai_tutor/agents/tutor.py` - Skip profile loading in demo mode

**Impact**: -200 lines of active code, simpler flow, faster responses

---

### Priority 3: Simplify Session Management (1-2 hours)
**Why**: Daily rotation and turn pruning add complexity without demo value

**Action**:
1. In demo mode, use simple session key: `f"demo_{learner_id}"`
2. Skip daily rotation and turn pruning
3. Keep SQLite storage but simpler logic

**Files to modify**:
- `src/ai_tutor/agents/tutor.py` - Simplify `_get_session()` when demo_mode
- Keep session storage but remove rotation logic

**Impact**: -100 lines, simpler debugging, faster startup

---

### Priority 4: Simplify Routing (1-2 hours)
**Why**: LLM-based routing adds latency and complexity

**Action**:
1. Use keyword-based routing only (already exists)
2. Remove LLM routing fallback in demo mode
3. Keep deterministic routing

**Files to modify**:
- `src/ai_tutor/agents/tutor.py` - Skip `_route_with_llm()` in demo mode
- `src/ai_tutor/agents/routing.py` - Document demo mode behavior

**Impact**: Faster responses, simpler code path

---

### Priority 5: Simplify Configuration (30 min)
**Why**: Too many options can overwhelm demo users

**Action**:
1. Create `config/demo.yaml` with minimal settings
2. Update README to show demo config usage
3. Keep full config for production

**Files to create/modify**:
- `config/demo.yaml` - Minimal demo config
- `README.md` - Add demo config section

**Impact**: Clearer demo setup

---

### Priority 6: Make MCP Optional (Documentation) (15 min)
**Why**: Keep MCP but clarify it's optional for demo

**Action**:
1. Update README to mark MCP as "Optional/Advanced"
2. Add note that demo works without MCP
3. Keep MCP code intact

**Files to modify**:
- `README.md` - Clarify MCP is optional
- `docs/demo.md` - Remove MCP from required setup

**Impact**: Clearer demo instructions

---

## 📊 Expected Impact After These Steps

### Code Reduction
- Personalization (demo mode): ~200 lines disabled
- Session management: ~100 lines simplified
- Routing: ~50 lines simplified
- **Total**: ~350 lines simplified/disabled

### Performance Improvements
- Faster responses (no LLM routing in demo)
- Faster startup (no personalization init)
- Simpler debugging (no session rotation)

### Maintainability
- Demo mode flag makes it easy to toggle features
- Production code remains intact
- Clear separation between demo and production

---

## 🚀 Implementation Order

1. **Add Demo Mode Flag** (30 min) - Foundation for everything else
2. **Disable Personalization in Demo** (2-3 hours) - Biggest impact
3. **Simplify Sessions** (1-2 hours) - Medium impact
4. **Simplify Routing** (1-2 hours) - Performance improvement
5. **Simplify Config** (30 min) - Polish
6. **Update MCP Docs** (15 min) - Clarification

**Total Estimated Time**: 5-8 hours

---

## 💡 Quick Win: Start with Demo Mode Flag

The demo mode flag is the foundation - it allows us to:
- Keep all production code intact
- Toggle features on/off easily
- Test both modes
- Gradually simplify without breaking production

Let's start there!

