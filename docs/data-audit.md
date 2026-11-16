# 資料流程稽核(tools/audit_data.py 產生)

實體 2048、來源 1492、關係 4088(auto 15、approved 3771、review 271、rejected 31)。

## 硬性錯誤:0 項

無。

## 警告:177 項(不阻擋建圖,列出供人工判斷)

- **formal edge without a verbatim quote in evidence**:9
  - `berger -extend-> ideology`
  - `sontag -extend-> benjamin`
  - `new_topographics_1975 -influence-> deadpan`
  - `nakahira_plants -belongs_to-> nakahira`
  - `moriyama_bye -belongs_to-> moriyama`
  - `becher_typologies -belongs_to-> becher`
  - `coburn -belongs_to-> photo_secession`
  - `f64 -extend-> straight_photography`
  - `tapp_und_tastkino_tap_and_touch_cinema_export_valie_w -belongs_to-> export_valie`
- **formal edge resting only on a book (no URL, no page): cited source**:8 條,來源:`newhall_history_s`×2、`about_looking`×1、`on_photography`×1、`new_topographics`×1、`nakahira_plants_s`×1、`moriyama_bye_s`×1、`becher_typ_s`×1
- **verification URL on a wiki, blog, bookseller or auction host (primary-text scans excepted)**:1
  - `moriyama -influence-> kurata_seiji: https://phillips.com/article/11848907/the-tattooed-man-seiji-kurata-and-flash-up`
- **entity with no formal edge (isolated dot in the viewer)**:2
  - `workshop_mag_w`
  - `lucie_rie`
- **work with no person author**:20
  - `provoke_journal`
  - `lightaura_zh`
  - `october5_w`
  - `aiz`
  - `nachtwey_war_photographer_w`
  - `lucken_taki_koji_counter_photography_w`
  - `cohen_meskin_photographs_not_transparent_w`
  - `kai_arinomama_no_image_w`
  - `jinchaji_pictorial_w`
  - `liangyou_journal_w`
  - `chen_shuxia_departing_socialist_realism_w`
  - `xu_yong_april_photo_society_w`
  - `hkipf_hong_kong_portfolio_vol1_w`
  - `nunaheduo_dislocation_w`
  - `barthes_camera_lucida_ja_w`
  - `sontag_on_photography_ja_w`
  - `benjamin_short_history_ja_w`
  - `berger_ways_of_seeing_ja_w`
  - `sontag_regarding_pain_ja_w`
  - `barthes_camera_lucida_zh_cn_w`
- **source cited by no relation**:137
  - `another_way`
  - `photographic_message`
  - `uncommon_places`
  - `american_photographs`
  - `eggleston_guide`
  - `photography_theory`
  - `thinking_photography`
  - `burden_rep`
  - `practices_looking`
  - `new_documents`
  - `moma_photo`
  - `aperture`
  - `george_eastman`
  - `wells_intro_s`
  - `steichen_fom_s`
  - `szarkowski_mw_s`
  - `bazin_ontology_s`
  - `debord_spectacle_s`
  - `azoulay_civil_s`
  - `dyer_ongoing_s`
  - `provoke_s`
  - `fukase_ravens_s`
  - `decisive_s`
  - `ballad_s`
  - `arbus_mono_s`
  - `on_photography_zh_s`
  - `camera_lucida_zh_s`
  - `lightaura_zh_s`
  - `camera_lucida_en_s`
  - `illuminations_s`
  - `americans_intro_s`
  - `arbus_retro_s`
  - `wos_bbc_s`
  - `met_nv_s`
  - `gaze_oneonta_s`
  - `whitney_bowery_s`
  - `flusser_pz_s`
  - `dada_montage_s`
  - `chapman_sekula_s`
  - `bourdieu_ms_s`
