#!/usr/bin/env bash
# Start a new feature following the complete Archon workflow
# Usage: scripts/start_feature.sh <feature-name> <bmad-facet> <description>

set -euo pipefail

# Input validation
FEATURE_NAME="${1:?Usage: scripts/start_feature.sh <feature-name> <bmad-facet> <description>}"
BMAD_FACET="${2:?Usage: scripts/start_feature.sh <feature-name> <bmad-facet> <description>}"
DESCRIPTION="${3:?Usage: scripts/start_feature.sh <feature-name> <bmad-facet> <description>}"

echo "🚀 Starting new feature: $FEATURE_NAME"
echo "📋 BMAD Facet: $BMAD_FACET"
echo "📝 Description: $DESCRIPTION"
echo

# 1. Create feature directory structure
echo "📁 Creating feature directories..."
mkdir -p "ai_docs/PRPs/feature-${FEATURE_NAME}/001"
mkdir -p "artifacts/feature-${FEATURE_NAME}/001"

# 2. Create PRP template
echo "📄 Creating PRP template..."
cat > "ai_docs/PRPs/feature-${FEATURE_NAME}/001/PRP.md" <<EOF
# PRP — feature-${FEATURE_NAME}/001: ${DESCRIPTION}

**BMAD Facet**: ${BMAD_FACET} - ${DESCRIPTION}

## Goal
[One sentence outcome describing what will be delivered]

## Inputs (named & minimal)
- [specific file paths and resources needed]
- [configuration files]
- [external dependencies]

## Constraints
- [Technical limitations]
- [Compatibility requirements]
- [Performance requirements]
- [Security considerations]

## Context Bits (curated)
- [Relevant examples]
- [Links to documentation]
- [Related patterns or standards]

## Runbook
1) [Specific implementation steps]
2) [In order of execution]
3) [With clear deliverables]
4) [Testing and validation]
5) [Artifact generation]

## Acceptance
- [Specific, testable criteria]
- [File existence and structure requirements]
- [Functional requirements]
- [Quality gates]
- [Documentation requirements]
EOF

# 3. Create initial artifacts
echo "📋 Setting up artifacts..."
cat > "artifacts/feature-${FEATURE_NAME}/001/notes.md" <<EOF
# ${DESCRIPTION} - Implementation Notes

## Summary
[Brief description of what this feature accomplishes]

## Implementation Progress
- [ ] PRP written and reviewed
- [ ] Implementation started
- [ ] Testing completed
- [ ] Documentation updated
- [ ] Quality gates passed

## Files Created
[List files as they are created]

## Files Modified
[List files as they are modified]

## Key Decisions
[Document important technical decisions]

## Testing Notes
[Document testing approach and results]

## Next Steps
[Track remaining work]
EOF

# 4. Create changed files CSV template
cat > "artifacts/feature-${FEATURE_NAME}/001/changed_files.csv" <<EOF
file_path,change_type,description
# Add entries as files are created/modified
EOF

# 5. Create feature branch
echo "🌿 Creating feature branch..."
git checkout -b "feature/${FEATURE_NAME}" 2>/dev/null || {
    echo "⚠️  Branch feature/${FEATURE_NAME} already exists, switching to it"
    git checkout "feature/${FEATURE_NAME}"
}

# 6. Generate SpecKit scaffold
echo "📋 Creating SpecKit scaffold..."
make spec NAME="${FEATURE_NAME}"

# 7. Create Obsidian planning note
if [[ -n "${OBSIDIAN_VAULT:-}" ]]; then
    echo "📚 Creating Obsidian planning note..."
    PLANNING_NOTE="${OBSIDIAN_VAULT}/feature-${FEATURE_NAME}-planning-$(date +%Y-%m-%d).md"
    cat > "$PLANNING_NOTE" <<EOF
# Feature Planning - ${FEATURE_NAME}

## 🎯 Feature Goal
${DESCRIPTION}

## 🏗️ BMAD Classification
**Primary Facet**: ${BMAD_FACET}

## 📋 Implementation Plan
- [ ] Complete PRP specification
- [ ] Begin implementation following runbook
- [ ] Run QA and validation
- [ ] Document and publish

## 🎨 Implementation Notes
- Technical approach
- Dependencies needed
- Risks to consider

## ✅ Acceptance Criteria
- [ ] Criterion 1
- [ ] Criterion 2
- [ ] Criterion 3

---
**Tags**: #prp #planning #${FEATURE_NAME}
**Status**: 📝 Planning
**Created**: $(date +%Y-%m-%d)
EOF
    echo "✅ Obsidian planning note created: $PLANNING_NOTE"
else
    echo "⚠️  OBSIDIAN_VAULT not set, skipping Obsidian planning note"
fi

# 8. Initial commit
echo "💾 Creating initial commit..."
git add "ai_docs/PRPs/feature-${FEATURE_NAME}/" "artifacts/feature-${FEATURE_NAME}/" "ai_docs/specs/${FEATURE_NAME}/"
git commit -m "feat: initialize ${FEATURE_NAME} feature (PRP feature-${FEATURE_NAME}/001)

Setup for: ${DESCRIPTION}

## Created
- PRP template for feature-${FEATURE_NAME}/001
- SpecKit scaffold for ${FEATURE_NAME}
- Artifacts directory structure
- Feature branch

BMAD Facet: ${BMAD_FACET}
Next: Complete PRP planning and begin implementation"

echo
echo "🎉 Feature ${FEATURE_NAME} initialized successfully!"
echo
echo "📋 Next Steps:"
echo "1. Edit ai_docs/PRPs/feature-${FEATURE_NAME}/001/PRP.md to complete the PRP"
echo "2. Review and update ai_docs/specs/${FEATURE_NAME}/ specification"
echo "3. Plan implementation in artifacts/feature-${FEATURE_NAME}/001/notes.md"
echo "4. Begin implementation following the PRP runbook"
echo
echo "🛠️ Quick Commands:"
echo "   make qa STORY=feature-${FEATURE_NAME}/001         # Run QA checks"
echo "   make verify-prp                                   # Check guardrails"
echo "   scripts/archon_impl_audit.sh feature-${FEATURE_NAME}/001  # Run audit"
echo "   OBSIDIAN_VAULT=\"\$HOME/Documents/ArchonVault\" make publish STORY=feature-${FEATURE_NAME}/001    # Publish to Obsidian when complete"
echo
echo "📂 Files Created:"
echo "   - ai_docs/PRPs/feature-${FEATURE_NAME}/001/PRP.md"
echo "   - ai_docs/specs/${FEATURE_NAME}/"
echo "   - artifacts/feature-${FEATURE_NAME}/001/"
if [[ -n "${OBSIDIAN_VAULT:-}" ]]; then
    echo "   - ${PLANNING_NOTE}"
fi
echo
echo "🌿 Branch: feature/${FEATURE_NAME}"
echo "Ready to start development! 🚀"