# Rendered press lists — the eleven rows a plain GET cannot read

Rendered 0 page(s), 166 already cached, 0 failed. Window start `2023-01-03`.

Playwright rendered these list pages and the HTML went into the same cache a plain fetch writes, so `ingest statements-press` consumes it unchanged. **Nothing in `statement-sources.yaml` was changed, and no release body was fetched for an unscreened row.**

`K000394` (Kim) is out of scope by owner decision: a 403 to our User-Agent and to a browser one is a bot wall, not a rendering problem.

## The seven still `owner_checked: false` — these need your screening

These were never rejected on content. They are unchecked because a plain fetch returned a page with zero dated items, so there was nothing to screen. Here is what each list actually contains now that it renders.

*(none)*

## The four already accepted, which came back `empty` from the real run

`owner_checked` is already true on these, so a plain `statements-press` run will collect them from the cache with no further decision.

### Martin Heinrich (`H001046`) — D senate — **COLLECTS**

* List: <https://www.heinrich.senate.gov/newsroom/press-releases>
* Releases in the window: **1413** over 89 page(s)
* Dates: 2023-01-05 to 2026-10-13 (does not reach the window start)
* What stands in the way: nothing — the rendered page reads, and this row collects from it
* Walk stopped: `window` — **complete**
* Rendered 156,333 bytes carrying 20 release-shaped link(s); dates on the page: 20 long, 20 ordinal, 0 ISO, 0 in permalinks
* What the list contains:
    1. Heinrich Demands Answers on Trump Administration Draining Strategic Petroleum Reserves to Dangerous Low Levels
    2. Heinrich Leads Resolution Recognizing Indigenous Peoples’ Day
    3. Zuni Tribe’s Request for Major Disaster Declaration Approved for July Storms and Flash Flooding Following Letter from N.M. Congressional Delegation
    4. What They’re Saying: Heinrich’s Bipartisan Permitting Reform Deal Will Deliver Cheaper Energy, More Jobs, Responsible Growth
    5. Heinrich Joins Jake Tapper on CNN To Discuss How Bipartisan American Affordability & Jobs Act Will Hold Data Centers Accountable, Force Data Centers to Pay For Electricity Grid Upgrades

### Darin LaHood (`L000585`) — R house — **COLLECTS**

* List: <https://lahood.house.gov/press-releases>
* Releases in the window: **229** over 24 page(s)
* Dates: 2023-01 to 2026-10
* What stands in the way: nothing — the rendered page reads, and this row collects from it
* Walk stopped: `window` — **complete**
* Rendered 85,696 bytes carrying 10 release-shaped link(s); dates on the page: 0 long, 0 ordinal, 0 ISO, 10 in permalinks
* What the list contains:
    1. LaHood Urges President Trump to Issue Presidential Major Disaster Declaration for Continued Recovery Efforts from August Storms
    2. ICYMI: LaHood, DelBene introduce Bipartisan Meals for Communities Tax Credit Act to Encourage Charitable Prepared Meal Donations
    3. LaHood's CHANGE Act Passes out of the Ways and Means Committee
    4. LaHood, Colleagues introduce Bipartisan Bill to Expand Access to Low-Interest Mortgages for First-Time Homebuyers
    5. LaHood Supports FY27 National Defense Authorization Act

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

### Josh Riley (`R000622`) — D house — **COLLECTS**

* List: <https://riley.house.gov/news/>
* Releases in the window: **101** over 6 page(s)
* Dates: 2025-01-03 to 2026-10-06 (does not reach the window start)
* What stands in the way: nothing — the rendered page reads, and this row collects from it
* Walk stopped: `exhausted` — archive ends at page 6 — **complete**
* Rendered 153,773 bytes carrying 20 release-shaped link(s); dates on the page: 0 long, 0 ordinal, 0 ISO, 20 in permalinks
* What the list contains:
    1. RILEY INTRODUCES BILL TO RESTORE HEALTH COVERAGE FOR 450,000 NEW YORKERS
    2. RILEY DEMANDS ANSWERS FROM VERIZON OVER RURAL LANDLINE SHUTOFFS
    3. RILEY INTRODUCES BIPARTISAN BILL TO IMPROVE TRANSIT ACCESS IN RURAL COMMUNITIES
    4. RILEY HELPS PASS BIPARTISAN BILL TO HOLD DATA CENTERS ACCOUNTABLE, LOWER UTILITY BILLS FOR UPSTATE NEW YORKERS
    5. HOUSE PASSES RILEY BILL TO CRACK DOWN ON “TRANQ,” THE DEADLY SEDATIVE MAKING FENTANYL EVEN MORE LETHAL

### Terri A. Sewell (`S001185`) — D house — **COLLECTS**

* List: <https://sewell.house.gov/press-releases>
* Releases in the window: **391** over 41 page(s)
* Dates: 2023-01 to 2026-09
* What stands in the way: nothing — the rendered page reads, and this row collects from it
* Walk stopped: `window` — **complete**
* Rendered 44,693 bytes carrying 10 release-shaped link(s); dates on the page: 0 long, 0 ordinal, 0 ISO, 10 in permalinks
* What the list contains:
    1. Rep. Sewell Leads Bipartisan Letter to Mexican Government Demanding Resolution for Birmingham-Based Vulcan Materials and Alabama Workers
    2. Rep. Sewell Accepting Applications for Military Service Academy Nominations
    3. Rep. Sewell Commemorates 63rd Anniversary of 16th Street Baptist Church Bombing and Honors Legacy of the Four Little Girls
    4. Reps. Sewell and Castor Introduce the Affordable Premiums for Seniors Act
    5. Rep. Sewell Marks 25 Years Since the September 11 Terrorist Attacks

### George Whitesides (`W000830`) — D house — **COLLECTS**

* List: <https://whitesides.house.gov/category/press-releases/>
* Releases in the window: **95** over 5 page(s)
* Dates: 2025-01-03 to 2026-10-05 (does not reach the window start)
* What stands in the way: nothing — the rendered page reads, and this row collects from it
* Walk stopped: `exhausted` — archive ends at page 5 — **complete**
* Rendered 153,447 bytes carrying 20 release-shaped link(s); dates on the page: 0 long, 0 ordinal, 0 ISO, 20 in permalinks
* What the list contains:
    1. Rep. Whitesides Pushes for a National Film Tax Credit to Bring Production Jobs Back to Santa Clarita and the Antelope Valley
    2. Rep. Whitesides Introduces Bipartisan Legislation To Protect Children from Human-Like Chatbots
    3. Rep. Whitesides Introduces Bipartisan Bill Commemorating the 50th Anniversary of the Space Shuttle Enterprise Rollout in the Antelope Valley
    4. ICYMI: Rep. Whitesides Calls for Industry-Wide “Safety Stand-Down” on Frontier AI Development in Washington Post Op-ed
    5. Reps. George Whitesides, Maria Salazar, and Don Davis Introduce Bipartisan Bill to Protect Seniors From Wire Fraud

