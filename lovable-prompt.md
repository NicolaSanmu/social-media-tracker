# Lovable Prompt - Social Media Tracker Dashboard

## ⚠️ IMPORTANT: DO NOT use Lovable Cloud

When Lovable asks if you want to enable Lovable Cloud or auto-managed Supabase, **select NO**. We have our own Supabase database with data already. Use manual Supabase integration instead.

---

Copy the prompt below to Lovable:

---

Build a social media analytics dashboard with React, TypeScript, and Tailwind CSS that connects to an **existing** Supabase database.

## Supabase Connection (IMPORTANT - Use these exact credentials)

Create `src/lib/supabase.ts`:
```typescript
import { createClient } from '@supabase/supabase-js'

const supabaseUrl = 'https://yxyraynybhfsdjdtymdu.supabase.co'
const supabaseAnonKey = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inl4eXJheW55Ymhmc2RqZHR5bWR1Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjY0ODgzODEsImV4cCI6MjA4MjA2NDM4MX0.jcROqlSmqGOEsIGGFNdA3SX4hNzyYRE36eWfkHVo8NY'

export const supabase = createClient(supabaseUrl, supabaseAnonKey)
```

**Database already has data** - no need to create tables. Just read from existing tables.

## Existing Database Tables

- `accounts` - tracked social media accounts (platform, username, display_name, follower_count, following_count, post_count, bio)
- `posts` - individual posts/videos
- `post_metrics` - metrics snapshots (views, likes, comments, shares)
- `account_metrics` - follower history over time
- `posts_with_metrics` (VIEW) - posts joined with latest metrics

## Pages

### 1. Dashboard (`/`)
- Header with title "Social Media Tracker" and last update time
- Statistics cards row:
  - Total accounts card (with icon)
  - Per-platform cards showing: total followers, account count, post count
  - Platform colors: Instagram pink (#E1306C), TikTok black, YouTube red (#FF0000), Twitter blue (#1DA1F2)
- Accounts table with columns: Platform badge, Account name, Followers, Posts, "View Details" link
- Top 10 posts section showing: platform badge, username, caption (truncated), views, likes, comments, external link

### 2. Accounts (`/accounts`)
- Header with "Add Account" button (green)
- Platform filter buttons: All, Instagram, TikTok, YouTube, X/Twitter (active button uses platform color)
- Account cards grid (responsive: 1 col mobile, 2 tablet, 3 desktop):
  - Avatar circle with first letter (platform-colored background)
  - Display name and @username
  - Stats: Followers | Following | Posts
  - Bio (2 lines max)
  - Platform badge and "View Details" link
- Empty state message when no accounts
- Add Account Modal:
  - Platform dropdown (instagram, tiktok, youtube, twitter)
  - Username input
  - Cancel/Submit buttons
  - Insert to Supabase accounts table on submit

### 3. Account Detail (`/account/:id`)
- Back link to accounts
- Account header: avatar, name, username, platform badge, bio
- Action buttons: "Visit Profile" (blue external link), "Delete" (red with confirmation)
- Stats row: Followers, Following (large formatted numbers)
- Two charts side by side:
  - Engagement Trends: line chart with Views (blue), Likes (pink), Comments (green)
  - Followers History: line chart (purple)
- Posts section:
  - Date range filter with From/To inputs
  - Quick date buttons: Last 7/30/90 days, This month, Last month, This year
  - Sort by dropdown: Date, Views, Likes, Comments, Shares
  - Order: Descending/Ascending
  - Posts table: Date, Caption, Views, Likes, Comments, Shares, Link
  - Sortable column headers with direction indicators

## Design
- Clean and simple with colorful data visualization
- White background, subtle shadows, rounded corners
- Numbers formatted with commas (1,234,567)
- Responsive mobile-first design
- Use Recharts for charts

## Supabase Queries

```javascript
// Dashboard - get accounts
const { data: accounts } = await supabase.from('accounts').select('*')

// Dashboard - get top posts with account info
const { data: topPosts } = await supabase
  .from('posts_with_metrics')
  .select('*, accounts(username, display_name)')
  .order('views', { ascending: false })
  .limit(10)

// Accounts - filter by platform
const { data: accounts } = await supabase
  .from('accounts')
  .select('*')
  .eq('platform', 'instagram')

// Accounts - add account (insert only basic info, data collected separately)
const { data, error } = await supabase
  .from('accounts')
  .insert({
    platform,
    username,
    display_name: username,
    account_id: username,
    follower_count: 0,
    following_count: 0,
    post_count: 0
  })

// Accounts - delete
await supabase.from('accounts').delete().eq('id', accountId)

// Account Detail - get posts with filters
const { data: posts } = await supabase
  .from('posts_with_metrics')
  .select('*')
  .eq('account_id', accountId)
  .gte('published_at', dateFrom)
  .lte('published_at', dateTo)
  .order(sortBy, { ascending: false })

// Account Detail - get metrics history for chart
const { data: history } = await supabase
  .from('account_metrics')
  .select('collected_at, follower_count')
  .eq('account_id', accountId)
  .order('collected_at', { ascending: true })
```

## Important Notes

1. **No authentication needed** - this is a public read dashboard
2. **Database already exists with data** - just connect and read
3. **Data collection happens externally** via Python scripts, not in this frontend
4. **Do NOT use Lovable Cloud** - use manual Supabase connection with the credentials above

---

## After Creating the Project

If Lovable asks about Supabase:
- Say NO to "Lovable Cloud" or "auto-managed database"
- Use the manual connection with credentials provided above
- The database already has tables and data - no migrations needed
