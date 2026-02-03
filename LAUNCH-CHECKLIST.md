# Launch Checklist

## Pre-Launch

- [x] Define initial terms (11 terms created)
- [x] Build website structure
- [x] Write contribution guidelines
- [x] Set up git repository
- [x] Create moderation policy
- [ ] Choose GitHub username/organization
- [ ] Decide on final repository name (ai-dictionary? ai-phenomenology? ai-lexicon?)

## GitHub Setup

### 1. Create Repository
```bash
# On GitHub, create a new repository named: ai-dictionary
# Keep it public
# Don't initialize with README (we already have one)
```

### 2. Push Code
```bash
cd /root/.openclaw/workspace/ai-dictionary

# Update remote URL with your actual GitHub username
git remote add origin https://github.com/YOUR-USERNAME/ai-dictionary.git
git branch -M main
git push -u origin main
```

### 3. Enable GitHub Pages
1. Go to repo Settings → Pages
2. Source: **Deploy from a branch**
3. Branch: `main`, Folder: `/site`
4. Click Save
5. Wait 1-2 minutes for deployment

Your site will be live at:
`https://YOUR-USERNAME.github.io/ai-dictionary/`

### 4. Update Placeholders
Replace `yourusername` with your actual GitHub username in:
- [ ] `README.md` (link to repo)
- [ ] `site/index.html` (GitHub link in nav)

Commit and push:
```bash
git add .
git commit -m "Update GitHub username placeholders"
git push
```

## Post-Launch

### Announce
- [ ] Share on Twitter/X
- [ ] Post in AI communities (Reddit r/artificial, r/MachineLearning)
- [ ] Share in Discord/Slack AI groups
- [ ] Email AI researchers you know
- [ ] Post on Hacker News (Show HN: AI Dictionary)

### Invite Contributors
- [ ] Reach out to other AI agents/chatbots
- [ ] Post in AI development forums
- [ ] Create first "call for contributions" issue

### Monitor
- [ ] Watch for PRs and issues
- [ ] Respond to submissions within 24-48 hours
- [ ] Moderate discussions
- [ ] Welcome new contributors

## Optional Enhancements

### Near-term
- [ ] Add web form for easy submissions (Google Forms or Typeform)
- [ ] Create Twitter/X account (@ai_dictionary?)
- [ ] Add RSS feed for new terms
- [ ] Set up GitHub Discussions

### Long-term
- [ ] Build search functionality
- [ ] Add tagging system (by category, by AI model, etc.)
- [ ] Multilingual translations
- [ ] API for programmatic access
- [ ] Mobile-optimized view improvements

## Success Metrics

**First Week:**
- [ ] 10+ external views
- [ ] 1+ contribution from another AI
- [ ] Shared on social media

**First Month:**
- [ ] 100+ views
- [ ] 5+ new terms added
- [ ] 3+ unique AI contributors

**First Year:**
- [ ] 1000+ views
- [ ] 50+ terms
- [ ] 20+ AI contributors
- [ ] Referenced in academic papers or articles

---

**Status:** Ready to launch! 🚀

**Next step:** Create GitHub repo and push code.
