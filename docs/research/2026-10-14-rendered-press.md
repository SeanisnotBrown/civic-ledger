# Rendered press lists — the eleven rows a plain GET cannot read

Rendered 0 page(s), 11 already cached, 0 failed. Window start `2023-01-03`.

Playwright rendered these list pages and the HTML went into the same cache a plain fetch writes, so `ingest statements-press` consumes it unchanged. **Nothing in `statement-sources.yaml` was changed, and no release body was fetched for an unscreened row.**

`K000394` (Kim) is out of scope by owner decision: a 403 to our User-Agent and to a browser one is a bot wall, not a rendering problem.

## The seven still `owner_checked: false` — these need your screening

These were never rejected on content. They are unchecked because a plain fetch returned a page with zero dated items, so there was nothing to screen. Here is what each list actually contains now that it renders.

### Martin Heinrich (`H001046`) — D senate — **STILL EMPTY**

* List: <https://www.heinrich.senate.gov/newsroom/press-releases>
* Releases in the window: **0** over 1 page(s)
* Dates: — to — (does not reach the window start)
* What stands in the way: 20 release links, each carrying its date as "October 13th, 2026" — **an ordinal suffix**, which `_DATE_LONG` does not match. A one-token regex change, not a judgement
* Walk stopped: `empty` — no dated releases on the first page — **a floor, not a total**
* Rendered 156,333 bytes carrying 20 release-shaped link(s); dates on the page: 0 long, 20 ordinal, 0 ISO, 0 in permalinks
* What the list contains:
    1. October 13th, 2026  Heinrich Demands Answers on Trump Administration Draining Strategic Petroleum Reserves to Dangerous Low Levels
    2. October 12th, 2026  Heinrich Leads Resolution Recognizing Indigenous Peoples’ Day
    3. October 9th, 2026  Zuni Tribe’s Request for Major Disaster Declaration Approved for July Storms and Flash Flooding Following Letter from N.M. Congressional Delegation
    4. October 9th, 2026  What They’re Saying: Heinrich’s Bipartisan Permitting Reform Deal Will Deliver Cheaper Energy, More Jobs, Responsible Growth
    5. October 7th, 2026  Heinrich Joins Jake Tapper on CNN To Discuss How Bipartisan American Affordability & Jobs Act Will Hold Data Centers Accountable, Force Data Centers to Pay For Electricity Grid Upgrades

### Mike Johnson (`J000299`) — R house — **STILL EMPTY**

* List: <https://mikejohnson.house.gov/media/>
* Releases in the window: **0** over 1 page(s)
* Dates: — to — (does not reach the window start)
* What stands in the way: **the release list is still not in the page, even rendered** — no link on it has the shape of a release, so this is not a date problem
* Walk stopped: `empty` — no dated releases on the first page — **a floor, not a total**
* Rendered 27,769 bytes carrying 0 release-shaped link(s); dates on the page: 0 long, 0 ordinal, 0 ISO, 0 in permalinks
* What the list contains: nothing a render could read

### Darin LaHood (`L000585`) — R house — **STILL EMPTY**

* List: <https://lahood.house.gov/press-releases>
* Releases in the window: **0** over 1 page(s)
* Dates: — to — (does not reach the window start)
* What stands in the way: 10 release links, 10 of them carrying the date **only in the URL** (`/2026/10/…`). **Owner decision:** does a publisher's own permalink date count as the statement's date?
* Walk stopped: `empty` — no dated releases on the first page — **a floor, not a total**
* Rendered 85,696 bytes carrying 10 release-shaped link(s); dates on the page: 0 long, 0 ordinal, 0 ISO, 10 in permalinks
* What the list contains:
    1. LaHood Urges President Trump to Issue Presidential Major Disaster Declaration for Continued Recovery Efforts from August Storms
    2. ICYMI: LaHood, DelBene introduce Bipartisan Meals for Communities Tax Credit Act to Encourage Charitable Prepared Meal Donations
    3. LaHood's CHANGE Act Passes out of the Ways and Means Committee
    4. LaHood, Colleagues introduce Bipartisan Bill to Expand Access to Low-Interest Mortgages for First-Time Homebuyers
    5. LaHood Supports FY27 National Defense Authorization Act

### Thomas Massie (`M001184`) — R house — **STILL EMPTY**

* List: <https://massie.house.gov/media/>
* Releases in the window: **0** over 1 page(s)
* Dates: — to — (does not reach the window start)
* What stands in the way: **the release list is still not in the page, even rendered** — no link on it has the shape of a release, so this is not a date problem
* Walk stopped: `empty` — no dated releases on the first page — **a floor, not a total**
* Rendered 27,514 bytes carrying 0 release-shaped link(s); dates on the page: 0 long, 0 ordinal, 0 ISO, 0 in permalinks
* What the list contains: nothing a render could read

### Mike Rounds (`R000605`) — R senate — **STILL EMPTY**

* List: <https://www.rounds.senate.gov/newsroom/press-releases>
* Releases in the window: **0** over 1 page(s)
* Dates: — to — (does not reach the window start)
* What stands in the way: 20 release links and NO date anywhere on the page
* Walk stopped: `empty` — no dated releases on the first page — **a floor, not a total**
* Rendered 392,692 bytes carrying 20 release-shaped link(s); dates on the page: 0 long, 0 ordinal, 0 ISO, 0 in permalinks
* What the list contains:
    1. Rounds Calls for Federal Gas and Diesel Tax Suspension to Lower Prices at Pump, President Trump to Invoke Defense Production Act
    2. Rounds Issues Statement Following Release of USPS OIG Report on South Dakota Mail Service
    3. Rounds Introduces RANCH Act to Help Rebuild America’s Cattle Herd
    4. Rounds Introduces Bipartisan Bill to Preserve Records for At-Risk Afghan Allies
    5. Rounds Introduces Legislation to Boost American Manufacturing of Robotics, Stay Ahead of China

### Jeanne Shaheen (`S001181`) — D senate — **STILL EMPTY**

* List: <https://www.shaheen.senate.gov/news>
* Releases in the window: **0** over 1 page(s)
* Dates: — to — (does not reach the window start)
* What stands in the way: 10 release links and NO date anywhere on the page
* Walk stopped: `empty` — no dated releases on the first page — **a floor, not a total**
* Rendered 112,016 bytes carrying 10 release-shaped link(s); dates on the page: 0 long, 0 ordinal, 0 ISO, 0 in permalinks
* What the list contains:
    1. In New Video, Shaheen Underscores Nationwide Impact of INSULIN Act, Highlights That Most States Do Not Cap Monthly Insulin Costs at $35
    2. Shaheen Applauds Senate Passage of Bipartisan Resolution to Establish October 7 as Energy Efficiency Day
    3. Shaheen Marks 10-Year Anniversary of Her Landmark Survivors’ Bill of Rights Law to Empower Survivors of Sexual Assault
    4. See All Press Releases
    5. Shaheen hears tariff woes in Peterborough, celebrates community gains in Newport

### Terri A. Sewell (`S001185`) — D house — **STILL EMPTY**

* List: <https://sewell.house.gov/press-releases>
* Releases in the window: **0** over 1 page(s)
* Dates: — to — (does not reach the window start)
* What stands in the way: 10 release links, 10 of them carrying the date **only in the URL** (`/2026/10/…`). **Owner decision:** does a publisher's own permalink date count as the statement's date?
* Walk stopped: `empty` — no dated releases on the first page — **a floor, not a total**
* Rendered 44,693 bytes carrying 10 release-shaped link(s); dates on the page: 0 long, 0 ordinal, 0 ISO, 10 in permalinks
* What the list contains:
    1. Rep. Sewell Leads Bipartisan Letter to Mexican Government Demanding Resolution for Birmingham-Based Vulcan Materials and Alabama Workers
    2. Rep. Sewell Accepting Applications for Military Service Academy Nominations
    3. Rep. Sewell Commemorates 63rd Anniversary of 16th Street Baptist Church Bombing and Honors Legacy of the Four Little Girls
    4. Reps. Sewell and Castor Introduce the Affordable Premiums for Seniors Act
    5. Rep. Sewell Marks 25 Years Since the September 11 Terrorist Attacks

## The four already accepted, which came back `empty` from the real run

`owner_checked` is already true on these, so a plain `statements-press` run will collect them from the cache with no further decision.

### Mark Kelly (`K000377`) — D senate — **STILL EMPTY**

* List: <https://www.kelly.senate.gov/newsroom/press-releases/>
* Releases in the window: **0** over 1 page(s)
* Dates: — to — (does not reach the window start)
* What stands in the way: 7 release links and dates ARE on the page (8 long, 0 ISO), but none landed near enough to an anchor for the extractor to attach
* Walk stopped: `empty` — no dated releases on the first page — **a floor, not a total**
* Rendered 266,102 bytes carrying 7 release-shaped link(s); dates on the page: 8 long, 0 ordinal, 0 ISO, 0 in permalinks
* What the list contains:
    1. ICYMI: Kelly Writes Washington Times Op-Ed on Keeping Humans in Command as AI Transforms Warfare
    2. Support Rolls in from Policymakers and National Organizations for Kelly’s Make AI Work for Americans Act
    3. Kelly, Gallego Push to Protect Head Start Services for Arizona Families
    4. Kelly, Whitehouse Press EPA, AI Companies on Rollback of Public Input Rules for Data Center Air Permits
    5. Kelly, Gallego Celebrate Committee Passage of Bill to Restore the Grand Canyon’s North Rim

### Max L. Miller (`M001222`) — R house — **STILL EMPTY**

* List: <https://maxmiller.house.gov/press-releases>
* Releases in the window: **0** over 1 page(s)
* Dates: — to — (does not reach the window start)
* What stands in the way: **the release list is still not in the page, even rendered** — no link on it has the shape of a release, so this is not a date problem
* Walk stopped: `empty` — no dated releases on the first page — **a floor, not a total**
* Rendered 203,453 bytes carrying 0 release-shaped link(s); dates on the page: 3 long, 0 ordinal, 0 ISO, 0 in permalinks
* What the list contains: nothing a render could read

### Josh Riley (`R000622`) — D house — **STILL EMPTY**

* List: <https://riley.house.gov/news/>
* Releases in the window: **0** over 1 page(s)
* Dates: — to — (does not reach the window start)
* What stands in the way: 22 release links, 20 of them carrying the date **only in the URL** (`/2026/10/…`). **Owner decision:** does a publisher's own permalink date count as the statement's date?
* Walk stopped: `empty` — no dated releases on the first page — **a floor, not a total**
* Rendered 153,773 bytes carrying 22 release-shaped link(s); dates on the page: 0 long, 0 ordinal, 0 ISO, 20 in permalinks
* What the list contains:
    1. Subscribe to the Riley Report
    2. Subscribe to the Riley Report
    3. RILEY INTRODUCES BILL TO RESTORE HEALTH COVERAGE FOR 450,000 NEW YORKERS
    4. RILEY DEMANDS ANSWERS FROM VERIZON OVER RURAL LANDLINE SHUTOFFS
    5. RILEY INTRODUCES BIPARTISAN BILL TO IMPROVE TRANSIT ACCESS IN RURAL COMMUNITIES

### George Whitesides (`W000830`) — D house — **STILL EMPTY**

* List: <https://whitesides.house.gov/category/press-releases/>
* Releases in the window: **0** over 1 page(s)
* Dates: — to — (does not reach the window start)
* What stands in the way: 20 release links, 20 of them carrying the date **only in the URL** (`/2026/10/…`). **Owner decision:** does a publisher's own permalink date count as the statement's date?
* Walk stopped: `empty` — no dated releases on the first page — **a floor, not a total**
* Rendered 153,447 bytes carrying 20 release-shaped link(s); dates on the page: 0 long, 0 ordinal, 0 ISO, 20 in permalinks
* What the list contains:
    1. Rep. Whitesides Pushes for a National Film Tax Credit to Bring Production Jobs Back to Santa Clarita and the Antelope Valley
    2. Rep. Whitesides Introduces Bipartisan Legislation To Protect Children from Human-Like Chatbots
    3. Rep. Whitesides Introduces Bipartisan Bill Commemorating the 50th Anniversary of the Space Shuttle Enterprise Rollout in the Antelope Valley
    4. ICYMI: Rep. Whitesides Calls for Industry-Wide “Safety Stand-Down” on Frontier AI Development in Washington Post Op-ed
    5. Reps. George Whitesides, Maria Salazar, and Don Davis Introduce Bipartisan Bill to Protect Seniors From Wire Fraud

