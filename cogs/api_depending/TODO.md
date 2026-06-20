# TODO

## Create tables in the database:

- [ ] guild_data
  - uuid
  - level
  - xp_percent
  - territories
  - wars
  - raids
  - member_count
---
- [x] members
  - uuid
  - username
  - guild_rank
  - last_online
  - playtime
  - weekly
  - weekly_streak
  - contributed
  - contribution_rank
  - joined_guild
  - left_guild
  - total_guild_raids
  - wars
  - last_updated_timestamp

----

- [x] member_guild_raids
  - uuid
  - total
  - notg
  - nol
  - tcc
  - tna
  - wtp
  - aspects
  - next_aspect
  - latest_timestamp

---

- [ ] member_rank_history
  - id
  - uuid
  - old_rank
  - rank
  - timestamp

---

- [ ] member_playtime_history
  - id
  - uuid
  - playtime
  - timestamp

---

- [ ] member_contribution_history
  - id
  - uuid
  - contribution
  - timestamp

---

- [ ] member_contribution_rank_history
  - id
  - uuid
  - old_contribution_rank
  - contribution_rank
  - timestamp

---

- [ ] member_guild_join_leave_history
  - id
  - uuid
  - activity
  - timestamp

---

- [ ] wars
  - id
  - uuid
  - wars
  - timestamp
