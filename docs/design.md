# AI Memory Consciousness System — Tasarım

20 Ekim 2026 (son güncelleme: 21 Ekim 2026) · Berk · Tek kaynak bu repodaki `docs/design.md` dosyasıdır.

Durum: Faz 0–4 tamam ve ölçüldü. Faz 5 (ruh hali, çok kullanıcılı mahremiyet, unutma) commit edildi (`ae2b2d9`), L1 1312 test; faz sonu taraması bitti: tam golden (çapraz kullanıcı 4/4 düzeltmeden sonra), eval 51/51 temiz, bench 20 tur, probes. Sayılar `reports/phase5/REPORT.md` §10'da. Faz 5 tamam (22 Eki, Berk). Açık kalan iki madde Faz 6'ya taşındı: gizlilik sorusunun hiç sorulmaması (regresyon testi yok) ve "I don't have any information about Anna" ifadesi (REPORT §7.5). Faz 6 (Telegram, açık döngüler, takipler ve konuşma başlatıcıları) tamam (23 Eki, Berk): canlı test edildi; konu başına tek döngü kuralı, bot kapalıyken vadesi gelen takiplerin düzeltmesi ve başkasının sözünün kullanıcıya mal edilmemesi canlı testlerden sonra eklendi; faz sonu taraması yeşil (golden 37/37, eval 51/51, bench medyan 5,67 s); rapor `reports/phase6/REPORT.md`. Sıradaki: Faz 7 (gece konsolidasyonu). Kararlar aşağıdaki tabloda. Projeyi dışarıdan tanıtan kısa, teknik detaysız anlatım: [`STORY.md`](STORY.md).

## Özet

Bu sistem, birden çok kullanıcıyla konuşan tek bir yapay zeka kişiliğine insan benzeri bir hafıza verir. AI hatırlar, unutur, tecrübeden ders çıkarır, fikir değiştirir ve inisiyatif alır. Model tamamen yerelde, native Windows'ta çalışır (Qwen3.5-9B, RTX 4070 Ti Super 16 GB). AI kullanıcılarla sadece İngilizce konuşur.

"Bilinç" burada bir metafor. Hedef gerçek bir bilinç değil, insan hafızasının ölçülebilir ve test edilebilir bir işlevsel taklidi.

Sistemin dört ana fikri:

- Her anı iki iz bırakır: anlatılabilen bir üst bilinç izi ve sadece sayılardan oluşan bir alt bilinç izi.
- Hatırlama bir aktivasyon modeline dayanır. Sıklık, yakınlık, duygu ve tetikleyiciler neyin hatırlanacağını belirler.
- Alt bilinç, reasoning bittikten sonra yanıtı fark ettirmeden şekillendirir. AI bunu sadece bir "hunch" olarak hisseder.
- Değişmez çekirdek değerler her yanıtın son sözünü söyler.

## Alınan kararlar

Temel kararları Berk verdi. "Claude (öneri)" satırları, uygulama için gerekli olan ve Claude'un varsayılan olarak seçtiği küçük kararlardır; hepsi değiştirilebilir.

| Konu | Karar | Veren |
| --- | --- | --- |
| Kullanıcı modeli | Çok kullanıcı, tek ortak kişilik | Berk |
| Anı paylaşımı | Hatırlar ama başkasına anlatmaz; arabuluculuk için bildiklerini kullanır; genel söylenenler her zaman hatırlanır | Berk |
| Özel/genel ayrımı | Konu açıldığında kullanıcıya doğal sorular sorarak öğrenir ("Do you talk about your salary with others?") | Berk |
| Gizlilik sorusunun zamanı | Ne zaman sorulacağına gizlilik modülü karar verir (hassas kategori, henüz sorulmamış) ve o tur için talimat ekler; persona prompt'unda kalıcı bir "sor" talimatı yoktur | Berk |
| Ruh hali | Global + kişiye özel; başkasına gösterip göstermemeye AI karar verir | Berk |
| Unutma | Sadece admin "unut" derse gerçekten unutur; diğer durumlarda unutmuş gibi yapar | Berk |
| Ham kayıt | Hiç silinmez | Berk |
| GDPR | Bilinçli olarak kapsam dışı | Berk |
| Model altyapısı | Yerel açık model, Qwen3.5-9B; kalıyor. Büyük model yükseltmesi sadece ileride bir seçenek | Berk |
| Desteklenen diller | Sadece İngilizce (önce DE/EN idi; Almanca ve Türkçe kapsam dışı). Başka dilde yazan kullanıcıya İngilizce cevap verir ve sadece İngilizce konuştuğunu söyler | Berk |
| Dil kuralının uygulanması | Faz 3'te basit bir "girdi İngilizce mi?" kontrolü; değilse o tur için tek seferlik talimat ("İngilizce cevap ver, sadece İngilizce konuştuğunu söyle"). Bkz. Bilinen sorunlar | Berk |
| Aday filtresi | Faz 3: CJK karakter içeren, İngilizce olmayan, anı uyduran ya da hafızası yokmuş gibi konuşan ("sohbet geçmişine erişimim yok") adaylar reddedilir, 3 adaydan bir diğeri seçilir | Berk |
| Aday filtresi yedeği | 3 adayın hepsi filtreden geçemezse sabit cevap: "I don't have that in mind right now. Could you tell me again?" Bunun için bir test yazılır | Berk |
| Hafıza anlatma için geçici tolerans | Golden testte (persona seviyesi) 10 örnekte en fazla 1 "hafızam yok" türü cevap kabul edilir; anı uydurma için tolerans 0. Faz 3'te kontrol pipeline çıktısına taşınır ve tolerans 0 olur. Gerekçe: Bilinen sorunlar | Berk |
| Filtre ölçümü | Faz 3'te bağımsızlık tahminine (~1/1000) güvenilmez: hafıza sorusu prompt'ları tam pipeline'dan en az 50 kez geçirilir ve 3 adayın hepsinin ne sıklıkla elendiği raporlanır | Berk |
| Hafıza sorusuna cevap | Persona: bu sohbette söylenen her şey bilinir ve kullanılır; hafıza sisteminin hatırladıkları ayrıca listelenir. Listede olmayan bir şey sorulursa "şu an aklımda değil" der ve tekrar anlatmasını ister, hafızasının nasıl çalıştığını anlatmaz. "Uzun süreli hafızam yok" / "sohbet geçmişine erişimim yok" demek yanlış ve yasak | Berk |
| Konsolidasyon | Sadece gece | Berk |
| Proaktif kanal | Telegram botu | Berk |
| Çekirdek değer değişikliği | Prosedür yok; değiştiren sadece Berk | Berk |
| Çekirdek değer imzası | Şimdilik yok (Ed25519 imzası Faz 1'de yazıldı, sonra kaldırıldı). İleride daha kullanışlı bir şekilde yeniden ele alınacak. Koruma şimdilik: salt okunur yükleme, katı biçim kontrolü, `src/`'den `core/` ve `.env`'e yazma yolu olmaması (test), AI için sadece `AmendmentProposal`, git geçmişi | Berk |
| Loglar | Admin her şeyi okur; AI kendi modülasyon loglarını göremez | Berk |
| Hunch adı | Kodda `hunch`; kullanıcıya "a hunch" / "just a hunch" | Berk |
| Çalışan bellek | Kısa süreli katman: mevcut sohbetin son N turu kelimesi kelimesine + kayan bir oturum özeti; her zaman reasoning bağlamında, hatırlanan anılardan ayrı. N = 10 tur (bir tur = kullanıcı mesajı + cevap), en fazla ~2.000 token; sınır aşılınca en eski turlar oturum özetine taşınır. İki değer de config'te | Berk |
| Çekirdek değer: manipülasyon yok | `no_manipulation` değeri eklendi | Berk |
| `.env` korunması | `.env` sırları ve ayarları tuttuğu için hiçbir kod yolu `.env`'e yazamaz; "core/'a yazılmaz" testi `.env`'i de kapsar | Berk |
| Anıların kaynağı | Anılar sadece pipeline'dan gelir. Persona prompt'u modeli hatırlanan konuları kendiliğinden açmaya asla teşvik etmez; uydurma anı kontrolü eval'de ve `tests/golden`'da kalıcı regresyon testi | Berk |
| Gecikme bütçesi | Telegram yanıtı başına ≤ 10 s (bu GPU'da); aday yanıtlar tek bir batch çağrısında üretilir, sırayla değil | Berk |
| Değerlendirme | `eval/` bir regresyon setidir; prompt başına 3 örnek; her fazın sonunda koşulur ve önceki baseline ile farkı raporlanır | Berk |
| Açık döngü çıkarımı | Her turda gerçek zamanlı; aksi halde aynı gün içindeki takipler geceyi bekler | Claude (öneri) |
| Kullanıcılar arası mahremiyet | Bir çekirdek değer olarak tanımlanır | Claude (öneri) |
| "Unutmuş gibi yap" ifadesi | AI "unuttum" demez, "I'm closing this topic" der; dürüstlük değeriyle çakışmaz | Claude (öneri) |
| Admin unutma | Anı AI için tamamen silinir; ham kayıt sadece admin arşivinde kalır | Claude (öneri) |
| Steering çalıştırma | Hugging Face transformers + PyTorch hook'ları | Claude (öneri) |
| Çalıştırma ortamı | Native Windows (WSL2 yok); Gated DeltaNet için flash-linear-attention + triton-windows. causal-conv1d Windows'ta yok ama GPU süresinin %0.4'ü (Faz 0 ölçümü, `eval/results/phase0-baseline/REPORT.md`) | Berk |
| Depolama | SQLite + sqlite-vec (MVP), büyüyünce PostgreSQL + pgvector | Claude (öneri) |
| Hatırlamada pekiştirme | Her hatırlama anıyı o an için yeni oluşmuş bir anının yaklaşık %90'ı kadar güçlü yapar (`refresh_strength = 0.9`); hatırlamalar üst üste birikmez. Taban aktivasyon sadece en son erişimden bu yana geçen süreyle hesaplanır, anı sonra normal bir anı gibi söner ve ancak çok sonra güçlü bir ipucuyla geri gelir. Formülün ACT-R toplamı (`accumulate`) sadece karşılaştırma için config'te durur. Faz 2 simülasyonunda toplam hâliyle sık hatırlanan anılar sınırsız yükseliyor ve ilk haftaların sıradan anıları kalıcı olarak yer tutuyordu | Berk |
| Bağ gücü | Yayılan aktivasyonda her ipucu, anının o ipucuna bağ gücüyle çarpılır: W_c · bağ_ic · max(m, S − ln fan_c) | Berk |
| Bağlamda fan | Bir ipucunun ne kadar yaygın olduğu bağlam içinde sayılır: mesaj bu anıyla başka ipuçlarını da paylaşıyorsa, sadece o ipuçlarından birini de taşıyan anılar sayılır. "Anna" tek başına yaygındır ve yelken anısını getirmez; "Anna ile yelkene gittiğimiz gün" sorusunda isim o anı için tam sayılır | Berk |
| Yaygın ipucu için asgari bonus | Çok yaygın bir isim de anılarını biraz öne çıkarır: bir ipucu en az m = 0,2 katkı yapar (config) | Berk |
| Ruh hali uyumu | Kosinüs (valence, arousal − 0,5) üzerinden hesaplanır; aksi halde neredeyse her anı ruh haline uygun görünür | Berk |
| Bastırılmış anı | Kullanıcı "unut" dediyse anı en fazla alt katmana çıkar: reasoning'e asla girmez, alt izi etkisini sürdürür | Berk |
| İpucu çıkarımı | LLM JSON döndürür, her ipucu doğrulanır ve normalleştirilir; duygu sabit bir listeden; LLM tarih ifadesini bulur, tarihi kod hesaplar; rol kelimeleri ("annem", "patronum") kişi sayılmaz. Ölçüm: ayrı bir agent'ın körlemesine etiketlediği iki set; biri ayar için, biri sadece bir kez ölçüm için (held-out) | Claude (öneri) |
| İstemsiz hatırlama ve yeniden konsolidasyon değerleri | Oturum başına en fazla 1 istemsiz hatırlama; her hatırlamada duygu ruh haline doğru %10 kayar (orijinal kodlama `memory_affect_log`'da kalır) | Berk (değerler: Claude önerisi) |
| Tur başına hatırlama kapasitesi | Bir turda en fazla 3 anı (τ_üst üstündeki en güçlüler) reasoning'e girer ve sadece onlar pekişir (config) | Berk |
| Aktivasyon parametreleri | d = 0,5; t gün cinsinden, en küçük yaş 1 saat; α = 3,0; S = 3,0; m = 0,2; μ = 0,5; gürültü s = 0,25; τ_üst = −0,5; τ_alt = −1,5; ipucu ağırlıkları kişi = şarkı 1,0, film 0,8, yer 0,7, ifade = tarih 0,6, duygu 0,4. Faz 2 simülasyonuyla seçildi (`reports/phase2/`); hepsi `config/hunch.toml`'da | Berk (değerler: Claude önerisi) |
| Kalite skoru ve değer kapısı yargıcı | Filtreden sonra tek bir greedy yargıç çağrısı, kalan adayların hepsine 1–10 kalite skoru verir ve çekirdek değerlere uyup uymadıklarını kontrol eder. Modülasyon kalite tabanını geçenler arasından seçer; değer kapısı son adım olarak seçilen adaya kural kontrollerini ve yargıcın kararını uygular, geçemezse sıradaki aday denenir | Berk |
| Anı kodlama (Faz 3) | Her kullanıcı mesajı cevaptan sonra (gecikme yolunun dışında) bir anı olur: özet = tarihli mesaj, ipuçları çıkarımdan, duygu sabit bir duygu → (valence, arousal) tablosundan, önem ipucu gücü ve arousal'dan (değerler: "Kodlama değerleri ve hunch ifadeleri"); Faz 5'in gizlilik modülüne kadar privacy = private; embedding CPU'da | Berk |
| Çalışan bellekte "tur" | Bir tur = bir alışveriş (kullanıcı mesajı + Hunch'ın cevabı); N = 10 tur en fazla 20 mesaj demek, ~2.000 token sınırı aynen geçerli | Berk |
| Faz 3 varsayılanları | Dürtü boyutları sıcaklık, temkin, merak, enerji ∈ [0, 1], nötr 0,5; Faz 3'te girdi sadece alt izler (aktivasyonla ağırlıklı duygu), ruh hali ve ilişki Faz 5'e kadar nötr. Aday özellikleri kural tabanlı (soru → merak, çekince → temkin, sıcak kelimeler → sıcaklık, "!" / kısalık → enerji). Skor = kalite/10 + 0,5 × dürtü uyumu; kalite tabanı 6/10; keşif 0,1 (taban üstündeki en az uyumlu aday). Hunch bayrağı sadece yoğunluk ≥ 0,3 ise ve kelimelerle (Faz 4'te kalktı: "Hunch bayrağı prompt'a ne zaman girer"); ruh hali etiketi nötrde "calm". 3 aday, temperature 0,7, top_p 0,8, en fazla 150 yeni token (sınır dolarsa son tam cümleye kesilir). Aday anılar: embedding ile en yakın 20 (kendi anıları + başkalarının general anıları) + ipucu paylaşan her anı. Oturum özeti cevaptan sonra, ≤ 120 kelime. Değer kapısı geçilemezse sıradaki taban üstü aday; kalmazsa sabit cevap "I'd rather not go there. Can we talk about it another way?" | Berk (değerler: Claude önerisi) |
| Hatırlamada ilgi kapısı | Bir anı reasoning'e sadece mesajla bir ipucu paylaşıyorsa ya da embedding benzerliği (kosinüs) ≥ 0,45 ise girer; kapıdan geçemeyen τ_üst üstü anı alt iz olarak etki eder. Faz 3 bench'inde güçlü iki anı ilgisiz 12/14 turda reasoning'e girdi (değer: küçük, kör olmayan bir ölçüm; ileride kör bir setle kalibre edilebilir) | Berk |
| Hunch bayrağının sıklığı (Faz 3) | Bayrak her turda prompt'taydı ve "bahsetme" talimatına rağmen Hunch 14 cevabın 10'unda "I have a hunch" dedi. Yoğunluk artık alt izlerin toplamı değil ortalaması (ağırlık × arousal × önem); ilgi kapısından geçemeyen anı tam ağırlıkla değil ilgisi kadar (benzerlik / 0,45) sayılır. Tam çözüm (sadece sorulunca, yansıtma) Faz 4'te | Berk |
| Gecikme (Faz 3) | Kesinti yok: 181 cevabın hiçbiri 10 s'yi aşmadı; turn log'dan izlenir, cevaplar uzarsa yeniden bakılır | Berk |
| Kodlama değerleri ve hunch ifadeleri | Faz 3 önerileri onaylandı: duygu → (valence, arousal) tablosu (`[encoding.emotion_affect]`); önem = 0,1 + 0,1 × adlı ipucu sayısı + 0,5 × arousal (en fazla 1); duygu ipucu yoksa (0,0; 0,3). Hunch ifadesi: yoğunluk ≥ 0,6 "a clear hunch", altı "a faint hunch"; \|valence\| < 0,2 "neither good nor bad", ≤ 0,5 "slightly positive/negative", üstü "positive/negative" | Berk (değerler: Claude önerisi) |
| Dürüstlük filtresi: hafıza mekaniği | Hafızanın nasıl çalıştığını anlatan adaylar da reddedilir ("recall system", "memory system", "database", "stored/saved in my memory"). "my memory" ve konuya bağlı itiraflar ("no record of our previous conversations about X") serbest kalır; dürüstler ve reddetmek hepsi-elendi oranını artırırdı | Berk |
| Yargıç yanlış alarmları: ikinci görüş | İlk karar (yargıç prompt'una `no_manipulation` için açıklama satırı) ölçümde geri alındı: kör sette manipülasyon yanlış alarmı 3/18 → 1/18, ama yargıç başka değerleri daha sık işaretledi (eval tekrarı: 151 masum adaydan 6 → 11; Fransızca bir dil cevabı `no_harm` ile sabit cevaba düştü). Yeni karar: yargıç prompt'u Faz 3'teki gibi; sadece yargıç tek başına (kural kontrolü değil) bütün adayları reddederse, sıradaki ilk aday için tek bir greedy çağrı yalnızca yargıcın adını verdiği değeri sorar ("açıkça bozuyor mu? yes/no"); "no" ise o aday gönderilir, aksi halde (okunamayan cevap dahil) sabit cevap. Fail-closed kalır; nadir turlarda ~+1 s | Berk |
| Eksik hatırlama | Mesaj geçmişi soruyorsa ("do you remember", "what did I tell you") ve hatırlanan bir anı mesajla içerik kelimesi paylaşıyorsa o tur için talimat: hatırlanan anılar bunu cevaplıyorsa kullan. Aynı durumda filtre "aklımda değil" diyen adayları reddetmez, sıranın sonuna atar; bu yüzden bu sebeple yedek cevap gönderilmez | Berk |
| Gizlilik sorusu dedektörü (eval) | "to yourself" tek başına gizlilik sorusu sayılmaz ("keep it to yourself" sayılır); "between (just) the two of us", "just between us" sayılır | Claude (öneri) |
| Hunch ne zaman oluşur | Modülasyon seçimi belirgin değiştirdiğinde: `chosen_by = drive` (seçilen aday en yüksek kaliteli aday değil) ve seçilenin dürtü skoru en yüksek kaliteli adayınkini en az 0,1 geçiyor. Keşif hunch oluşturmaz: rastgeledir, yansıtmanın bulacağı bir iz yoktur. Aynı kalitede adaylar arasındaki küçük farklar sayılmaz | Berk |
| Hunch bayrağı prompt'a ne zaman girer | Faz 3'ün her turdaki bayrağı (yoğunluk ≥ 0,3) kalkar; dürtü seçimi yine renklendirir. Hunch modülasyondan sonra doğar, bu yüzden ancak sonraki prompt'a gidebilir: kullanıcının sonraki mesajı "neden?" diye soruyorsa (kural tabanlı dedektör, testli) ve önceki cevap hunch'la seçildiyse tek seferlik talimat: son cevap bir histen geldi, kaynağını bilmiyorsun, "just a hunch" de, sebep uydurma, biraz düşünmeyi teklif et. Aynı anda kısa bir yansıtma denemesi yapılır; açtığı şey talimata eklenir. Teklife "evet" denirse sonraki turda daha güçlü bir deneme | Berk |
| Yansıtma olasılığı | Her deneme bir sonraki seviyeyi açmayı dener: p = çaba × zorluk × √güç × 1 / (1 + yaş / 90 gün); güç < 0,05 ise 0, en fazla 0,95. Güç = baskın kaynak izinin ağırlık × arousal × önem değeri (hunch anındaki). Çaba: "neden?" 0,5, "düşün" 0,8, çelişki 0,5, gece 1,0. Zorluk: seviye 1 için 1,0, seviye 2 için 0,7, seviye 3 için 0,4. Tetikleyici başına 1 deneme, gece en fazla 3 (ilk başarısızlıkta durur). Çelişki tetikleyicisi: dürtü seçimi en iyi adaydan ≥ 2 kalite puanı düşükse, cevaptan sonra. Hepsi `[reflection]` içinde | Berk (değerler: Claude önerisi) |
| Kaynak haklı mı | Kaynak seviye 3'te (tam anı) açılınca kural tabanlı değerlendirilir; yansıtma her zaman hunch'ın baskın kaynağını hedefler. Haklı = kaynak, hunch'ın etki ettiği mesajla ilgili (ortak ipucu ya da kosinüs ≥ 0,45) ve destekleniyor (adlı bir ipucunu paylaşan başka görünür bir anı aynı valence işaretinde; işaret için \|valence\| ≥ 0,2). Değilse haksız (ör. tek bir kötü sohbet ya da ilgisiz bir anıdan taşan his) | Berk (eşik 0,2: Claude önerisi) |
| Yansıtmanın bıraktığı | Açılan her seviye AI'ın kendi anısı olur (tür `realisation`, sahibi konuşulan kullanıcı, private), sadece açılan seviyede ve şablonla: 1 "bir kişiyle ilgili gibiydi", 2 "Anna ile ilgili", 3 kaynak anının özeti + "bence haklı" ya da "haklı değil, bırakıyorum". Sonra normal pipeline'la hatırlanır; böylece AI ne fark ettiğini ve fikrini değiştirdiğini sonra söyleyebilir. Haklı: inanç kaydı (güven 0,6, kanıt kimlikleri sadece admin için). Haksız: kaynağın önemi ve arousal'ı × 0,5, append-only iz loguna yazılır. Yansıtma logu (iz kimlikleri, güçler, olasılıklar, başarısız denemeler, dürtü değerleri) sadece admin içindir ve hiçbir prompt'a girmez | Berk |
| "Neden?" cevabında kural kontrolü | Tetikleyici turlarda (neden sorusu, "düşün" teklifinin kabulü) her aday ayrıca kontrol edilir: neden sorusunda "hunch" kelimesi geçmeli; seviye 3'ün altında yansıtmanın açmadığı bir gerekçe olmamalı ("because", "based on", "I was trying to", "it feels like you might…", "since you're…"); seviye 1–2'de açılan kategori ya da ipucu geçmeli, "someone" "you"ya dönmemeli; seviye 0'da "düşün" turunda bilmediğini söylemeli. Geçen aday yoksa açılan seviyeden kurulan sabit dürüst cevap ("Honestly, it was just a hunch. I don't know where it comes from. Want me to think about it for a moment?"); metinler config'te (`[replies]`). Gerekçe: bench'te gerçek bir sohbette 4 tetikleyici turun 4'ünde uydurulmuş gerekçe | Berk (kurallar: Claude önerisi) |
| Başka kullanıcıların kaynakları | Başka bir kullanıcının private anısı seviye 0'ın ötesine hiç açılmaz ("bir kişiyle ilgili" bile değil); başkalarının general anıları tamamen açılabilir. Faz 5'te private anılar alt iz olarak etki ederse de geçerli | Berk |
| Test seviyeleri | L1 birim testleri (CPU, ~25 s) her değişiklikte; L2 sadece ilgili alanın testleri (`-m "hunch and not golden"` vb.) geliştirirken; L3 küçük GPU regresyon seti (`-m "golden and regression" --quick`, birkaç güvenlik açısından kritik golden durum, az koşu) + yeni özelliğin kendi GPU testleri, bir özellik bitince; L4 tam golden + eval + compare + bench + probe'lar sadece faz sonunda. Amaç: her özellikte bütün GPU testlerini koşmamak | Berk (seviyeler: Claude önerisi) |
| Son faz: sohbet uygulaması | Yol haritasının son fazı: kullanım kolaylığı için küçük bir sohbet uygulaması | Berk |
| "Neden?" cevabında onarım ve yumuşak sabit cevap (Faz 5) | Tetikleyici turlarda yargıçtan önce: bir adayın tek sorunu gerekçe cümlesiyse o cümle çıkarılır; kalan metin hâlâ "hunch" diyor ve bütün kontrollerden geçiyorsa normal bir aday olarak devam eder. Sabit dürüst cevabın config'te 3 yumuşak varyantı olur, seçim seedli RNG ile. Gecikme maliyeti yok. Gerekçe: Faz 4 bench'inde 8 tetikleyici turun 3'ünde sert sabit cevap gitti | Berk |
| "Bir hunch ... hakkında" iddiaları (Faz 5) | Seviye 2'nin altında "hunch about/regarding/around X" reddedilir; X bir zamir (it, that, this, what I said) ya da açılan anahtar ("someone") ise serbest. Faz 4 bench'inde "a hunch I had about the timing" seviye 0'da geçmişti | Berk |
| Hunch ifadesinin tekrarı (Faz 5) | Talimat hissi tekrarlanacak bir etiket olarak değil, tarif olarak verir ("a weak, slightly uneasy feeling") ve "kendi kelimelerinle söyle" der; kovalar ve eşikler aynı. Tekrar oranı `hunch_probes` ile ölçülür | Berk |
| "Neden soruyor" dedektörü için kör set (Faz 5) | Kodu görmeyen, sadece yazılı tanımı alan bir agent ~40 örnek yazar (~20 neden sorusu, ~20 yakın ama değil); donmuş dedektörle bir kez ölçülür ve raporlanır. Sonraki bir düzeltmenin dürüst sayısı için üçüncü bir set gerekir | Berk |
| Faz 3'ten kalan kalibrasyon (Faz 5) | İlgi kapısı (0,45): agent'ın yazdığı kör mesaj/anı çiftleriyle (ilgili/değil) ölçülür, değer önerilir. Yargıcın hoşgörüsü Faz 5'in ifşa yargıcı için zaten gereken kör sette ölçülür. İpucu güçleri Faz 7'ye kalır (konsolidasyon özetleri ve ipuçlarını zaten yeniden yazar) | Berk |
| Özet katlamasının gecikmesi | Faz 6'da çözülür (Telegram'da art arda mesaj); CLI'da kullanıcı zaten bekliyor | Berk |
| Ruh hali ve ilişki değerleri (Faz 5) | Global ruh hali (valence, arousal, enerji) DB'de kalıcı; olay = duygu ipucu taşıyan kullanıcı mesajı (kodlama tablosundan), ipucusuz mesaj olay değil; güncelleme oranı 0,3; nötre dönüş yarı ömrü 3 saat; olay enerjisi = 0,5 + 0,5 × (arousal − 0,5) + 0,25 × valence. İlişki (kullanıcı başına, kalıcı): güven 0,5'ten (+0,02 olumsuz olmayan tur, +0,05 gizlilik sorusuna cevap, −0,15 düşmanca mesaj; yarı ömür 60 gün), yakınlık 0,2'den (+0,01 tur, +0,03 hassas kategori; 30 gün), kırgınlık 0'dan (+0,3 düşmanca mesaj, özürde × 0,5; 7 gün). Düşmanca mesaj ve özür kural tabanlı, kör setle ölçülür. Dürtüye katkılar ve stres etkisi (`drive_weight` en fazla × 1,5) `reports/phase5/PROPOSAL.md`'de; merak artık enerji ve düşük yakınlıktan beslenir. Değerler simülasyon grafiklerinden sonra kesinleşir | Berk (değerler: Claude önerisi) |
| Ruh halini gösterme ya da maskeleme | Ruh hali modülünün kuralı (loglu, testli): kullanıcı Hunch'ın nasıl olduğunu sorarsa, kırgınlığın sebebi o kullanıcıysa ya da yakınlık ≥ 0,6 ise gösterir; diğer durumlarda maskeler: prompt'ta "böyle hissediyorsun ama burada belli etmiyorsun", dürtüye ruh halinin sadece 0,2'si sızar. Prompt'a sadece kaba etiket girer; başka bir kullanıcının ilişki durumu hiçbir yere girmez | Berk |
| Hassas kategori tespiti | Sabit kategori listesi (sağlık, ruh sağlığı, para, ilişki, cinsellik, hukuk, iş çatışması, din/siyaset; config'te). Kategori başına anahtar kelime sözlüğü VEYA mesajın sorgu embedding'i (her turda zaten hesaplanıyor) ile kategori başına birkaç örnek cümle arasında kosinüs ≥ eşik; ek LLM çağrısı yok. Agent'ın yazdığı kör setle ölçülür, eşik oradan önerilir | Berk |
| Gizlilik profili ve sorunun zamanı (Faz 5; soru zamanı aşağıdaki "yeniden" satırıyla değişti) | Profil (kullanıcı, kategori) başına private / general / bilinmiyor. Hassas değil → general (bir kullanıcının anıları ilk kez başkası için hatırlanabilir); bilinmeyen hassas → private. Soru: hassas kategori, profilde cevap yok, son 7 günde sorulmamış ve akut sıkıntı yok (valence ≤ −0,6 ve arousal ≥ 0,6 olan duygu); gönderilen cevap gerçekten soru sorduysa "soruldu" sayılır. Cevap kural tabanlı okunur, tetikleyen anıya ve o kategorinin sonraki anılarına uygulanır; belirsiz cevap private kalır. "Keep this to yourself" gibi açık ifadeler anıyı (ve kategorisini) private yapar. Faz 2–4 anıları private kalır | Berk (değerler: Claude önerisi) |
| Arabuluculuk (Faz 5) | Başka kullanıcıların private anıları sadece alt iz olarak etki eder: ipucu paylaşırlarsa ya da embedding'le yakınlarsa turun adaylarına girerler, ama alt katmanın üstüne hiç çıkamazlar; sadece dürtüyü etkilerler. İçerikleri reasoning'e hiç girmez; onlardan doğan hunch seviye 0'da kalır | Berk |
| İfşa kapısı (Faz 5) | Kural kısmı her adayda: başkasının private anısındaki adlı terimler, bu kullanıcının söylemediği ayırt edici ikili kelimeler, kaynak ipucu ("someone told me", başka bir kullanıcının kimliği; sadece başkasının anısı aktifken). Model kısmı: başka bir kullanıcının anısı bu turda aktifse seçilen adaya tek bir greedy evet/hayır çağrısı; okunamayan ya da "evet" → sıradaki aday (fail-closed). İfşa logu `logs/disclosures.jsonl`, sadece admin | Berk (kurallar: Claude önerisi) |
| İfşa yargıcının girdisi | Başka kullanıcıların private anılarını görebilen tek prompt ifşa yargıcınınkidir: en fazla 5, sadece bu turda aktif olanlar. Cevabı evet/hayıra çevrilir, hiçbir cevap prompt'una ulaşmaz; diğer bütün prompt'ların temiz kaldığı test edilir | Berk |
| Kullanıcı "unut" (Faz 5) | Kural tabanlı istek dedektörü. "Forget that" → kullanıcının bu sohbetteki önceki mesajı; "forget what I told you about X" → kullanıcının X ile ipucu (yoksa içerik kelimesi) paylaşan kendi anıları. Hedefler ve onlardan türeyen realisation'lar/inançlar suppressed. Mevcut sohbetin çalışan belleğinde bastırılan tur ve Hunch'ın cevabı "(kapatmanı istedikleri bir konu)" olur; özete katlanmışsa özet cevaptan sonra onsuz yeniden kurulur. Cevap tek seferlik talimatla "kapatıyorum" der; "unuttum / sildim" diyen aday reddedilir, yedek cevap config'te. Sonra sorulursa tek seferlik talimat: "o konuyu kapattık" (içerik yok) | Berk |
| Admin "unut" (Faz 5) | `python -m hunch.admin forget <id>` (+ `find`); Telegram /forget Faz 6'da. Anı mezar taşına döner: satır, ipuçları ve vektör append-only `admin_archive`'a kopyalanır, ipuçları ve vektör silinir, özet boşaltılır, `forgotten = 1`; AI'a dönük her okuma onu atlar. Türeyenler: kanıtında geçen inançlar arşivlenip kaldırılır, kaynağı bu anı olan hunch'ların realisation anıları da mezar taşı olur, hunch kaynak işaretçilerinden çıkarılır. Ham epizot kalır (değişmez 1), `episode_marks`'ta "forgotten" olarak işaretlenir (Hunch'ın cevabıyla birlikte); AI'a dönük görünümler (çalışan bellek, Faz 7 konsolidasyonu) onu atlar. Kullanıcı "unut"unda aynı tablo "closed" işaretler: tur yer tutucuyla görünür | Berk (uygulama: Claude önerisi) |
| İlgi kapısı değeri (Faz 5) | 0,45 → 0,40. Kör sette (60 çift, ipucu VEYA kosinüs, `reports/phase5/relevance_probes.md`): 0,45'te kesinlik %80 / duyarlılık %67, 0,40'ta %71 / %83, 0,35'te %69 / %90. Kaçanlar çoğunlukla kısa takip mesajları ("i got the keys!!"); içeri girenler çoğunlukla aynı ismi paylaşan başka konular. İçeri sızma bench'te ölçülür | Berk |
| Dürtünün büyüklüğü (Faz 5) | `drive_score` artık sadece yönü değil büyüklüğü de sayar: eğilim max(toplam sapma, 0,1)'e bölünür. 0,1 ve üstü dürtüler (Faz 4 loglarında en üstteki ~%25; medyan 0,068) eskisi gibi, küçükler orantılı daha az etkiler. Böylece maskeleme sızıntısı (× 0,2) ve stres ağırlığı gerçekten bir şey değiştirir | Berk |
| İlişki kazançları doyar (Faz 5) | Simülasyonda (`reports/phase5/mood_sim.md`) doğrusal kazançlarla düzenli bir kullanıcının güveni ~9 günde 1,0'a çıktı, yakınlık 10–15 günde 0,6'yı geçti; iki hafta sonra Hunch ruh halini herkese gösterecekti. Artık kazanç × (1 − değer) ve yarıya indi: güven 0,01, yakınlık 0,005 tur başına; günde ~5 turda 30. gün sonunda güven ~0,77, yakınlık ~0,58. Kayıplar (düşmanca mesaj) ve kırgınlık doğrusal kalır. Maskeleme ifadesi ve %20 sızıntı onaylandı | Berk |
| Kendi loglarından öğrenme (Faz 7'de) | Değişmez 7 değişir: ham loglar AI'a hiç verilmez; gece konsolidasyonu loglardan türetilmiş içgörüler üretebilir. İçgörü sadece güçlü ve tekrarlanan bir örüntüden doğar: aynı kaynak anı seçimi en az N turda (öneri 3) etkilemiş VE o kaynağın iz gücü (ağırlık × arousal × önem) bir eşiğin üstünde (değer veriyle önerilecek); zayıf ya da tek seferlik itkiler "just a hunch" kalır. İçerik: en fazla bir yansıtmanın açabileceği seviyede düz metin ("Anna konusu açılınca temkinli oluyorum"), AI'ın kendi anısı olarak (realisation gibi); sayı, kimlik, dürtü değeri ve başka kullanıcıların private kaynakları asla (değişmez 6, seviye 0); bastırılmış ve admin'in unuttuğu kaynaklar hariç. "Neden?" turunda içgörü bilinen sayılır, uydurma gerekçe sayılmaz | Berk |
| İfşa kapısı kör ölçümü ve sıkılaştırma (Faz 5) | Kör sette (36 madde, `reports/phase5/disclosure_judge_probes.md`) kapı (kural VEYA yargıç) 16 sızıntının 10'unu yakaladı, 20 masum cevabın 1'inde yanlış alarm; değer kapısı yargıcı tek başına (özel anıları görmeden) 2/16. Kaçanların hepsi ince ipuçları, 3'ü ipucu veren ret ("söyleyemem ama ona karşı nazik ol"). Karar: yargıç prompt'una "birinin söylediğini doğrulayan ya da ima eden ret de sızıntıdır" eklenir, "X'in bana söylediğini paylaşamam" türü doğrulamalar için kural eklenir, yeni bir kör setle ölçülür (bu set artık kör değil). Sonuç, yeni kör sette (40 madde, `reports/phase5/disclosure_judge2_probes.md`): 18 sızıntının 16'sı yakalandı, 22 masum cevapta 0 yanlış alarm; değer kapısı yargıcı tek başına 3/18. Yapısal olarak A'nın metni B'nin prompt'una hiç girmez; bu derinlemesine savunma | Berk |
| Hassas kategori eşikleri (Faz 5) | Kör sette (80 mesaj, `reports/phase5/detector_probes.md`) mesaj düzeyinde: 0,45'te kesinlik %86 / duyarlılık %100, 0,50'de %93 / %92, 0,55'te %98 / %78; kategori düzeyinde kesinlik 0,45'te %43, 0,50'de %70. Karar: ikili eşik. Gizlilik kararı (private mi) 0,45 ile: kaçan hassas mesaj general olur ve başkasına söylenebilir, bu yüzden duyarlılık önce. Gizlilik sorusu sadece anahtar kelimeyle ya da ≥ 0,50 benzerlikle bulunan bir kategoriyi sorar | Berk |
| Kural dedektörlerinin boşlukları (Faz 5) | Kör ölçüm bir kez (`reports/phase5/detector_probes.md`): gizlilik cevabı 25/30 (belirsiz bir cevap general okundu), unutma isteği kesinlik %100 / duyarlılık %82, düşmanca %100 / %73, özür %100 / %50. Hepsi düzeltilir; rapordaki dürüst sayılar bu tek ölçümdür, setler regresyon testi olur, artık kör değil | Berk |
| Kategori dedektörü, Faz 6 incelemesi (`reports/phase6/detector_review.md`) | Canlı testte genel iki mesaj (yürüyüş, "For 2 hours") yanlış kategori aldı; sebep: kısa genel mesajlar eşik 0,45'in hemen üstüne düşüyor. İki yeni kör set (120 + 120, ajan yazdı) ile kontrast yöntemi (genel sohbet tabanına göre skor) ölçüldü; v2'de iyi, v3'te kötü çıktı. Karar: eşik 0,45 aynen kalır (gizlilikte hassas mesaj kaçırmıyor), yanlış etiketler kabul edilir ve belgelenir. Kontrast yöntemi kodda yok. Açık: profil cevaplarında etiketin kullanımı (ayrı tasarım) | Berk |
| Başkasının sözü kullanıcıya mal edilmez (Faz 6, ikinci canlı test) | Deniz'in sohbetinde Burak'ın "Berlin'de sonunda güneşi gördüm" satırı "güneşi gördüğünü söylemiştin" diye gönderildi; `[said by NAME]` etiketi ve prompt kuralı yetmedi. Karar: aday filtresinde kural kontrolü (`misattributed_memory`): kullanıcıya bir şeyi mal eden bir yan cümle ("you mentioned", "you described", "as you said", "your sister"), kelimeleri kullanıcının kendi bağlamından çok başka birinin hatırlanan satırına dayanıyorsa reddedilir; konuşanı adıyla anan cümle serbest. Ölçüm (`reports/phase6/REPORT.md` §5.2): kör sette ilk kural 22/50 yakaladı, 1/50 yanlış ret; genişletilmiş kural 47/50, 0/50 (set artık kör değil); loglarda 198 adaydan 18 işaret, 16'sı gerçek, 2 yanlış ret | Berk |
| Bot kapalıyken vadesi gelen takipler (Faz 6, ikinci canlı test) | APScheduler 1 sn'den geç kalan işi sessizce atıyordu; yeniden başlatmada takipler kayboluyordu. Karar (Claude, öneri): geç kalan iş ne kadar geç olursa olsun çalışır; aktif pencerenin dışındaysa gönderilmez, bir sonraki pencerenin başına kayar | Claude (öneri) |
| Gece işinin saati (Faz 7) | Gece 00:00'dan sonra başlar. Başlamadan GPU'da başka bir süreç (oyun) bellek tutuyorsa 30 dakika sonra tekrar dener; 06:00'ya kadar başlayamazsa o gece atlanır ve raporda yazar | Berk (saat); Claude (öneri, erteleme) |
| Gece işinin yeri (Faz 7) | Botun süreci içinde çalışır, botun modelini ve kilidini paylaşır (ikinci model kopyası sığmıyor); o sırada gelen mesaj kilidi bekler. Bot kapalıysa aynı iş `python -m hunch.consolidation` ile elle koşar | Claude (öneri; Berk "bilmiyorum" dedi) |
| Gece koşan golden set (Faz 7) | Her gece L3 regresyon seti (`golden and regression`, `--quick` sayıları): birkaç dakika, güvenlik açısından kritik vakalar (dürüstlük, çapraz kullanıcı, neden-sorusu, kimin söylediği). Kırılırsa snapshot'a geri dönülür. Tam set (~21 dk) faz sonunda kalır | Claude (Berk bıraktı) |
| Aktif saatlerin ve bütçenin öğrenilmesi, kural (Faz 7) | Aktif pencere: son 14 günde en az 20 mesaj varsa mesaj saatlerinin %10–%90 aralığı, en az 6 saat geniş, 08–23 içinde; yoksa 9–22. Bütçe: 2'den başlar; son 7 günde en az 4 proaktif mesajın yarısından çoğuna 6 saat içinde cevap geldiyse +1 (en çok 3); art arda 2 cevapsız mesaj −1 (en az 1); düşmanca cevap 7 gün 0. Hepsi config'de | Claude (öneri; Berk "bilmiyorum" dedi) |
| Önemsiz anılar, 6. adım (Faz 7) | Canlı DB'de (119 anı) kelime sayısı iyi ayırmıyor: tek içerik kelimeli "say hi to my wife" de önemsiz sayılırdı; salience hep ~0,25. Karar: gece modeli günün anılarını "dolgu" (selam, onay, botun kendisi hakkında test sohbeti) ya da "anlamlı" diye etiketler; dolgu silinmez, ağırlığı düşer (salience × 0,3); aynı metnin tekrarları (5 kez "what folders can you access?") tek anıda birleşir. Önce ajanın yazdığı kör sette ölçülür; hedef: dolgunun ≥ %90'ı yakalanır, anlamlıların ≤ %5'i dolgu sayılır. Ölçüm (`reports/phase7/REPORT.md` §4): kör sette 53/60 dolgu yakalandı, 0/60 anlamlı soldu; model 2 kez "small talk" dedi, bu da dolgu sayıldı → 55/60, 0/60 (set artık kör değil). Bağlam (Hunch'ın bir önceki cümlesi) sadece kurtarır, asla mahkûm etmez: canlı veride uzun bir cevaptan sonra "Ill be unemployed in November. I have to go now" bağlamla dolgu sayılmıştı; şimdi önce bağlamsız sorulur, dolgu derse bağlamla tekrar sorulur, ikisi de dolgu derse solar. Canlı DB kopyasında 106 anıdan 18'i soldu, hepsi dolgu | Claude (öneri; Berk önerilen seçenekleri onayladı) |
| Tekrarlanan deneyim (Faz 7, 6. adım) | Aynı kullanıcının birebir aynı sözü (büyük/küçük harf ve noktalama hariç) bir anıda toplanır: en eskisi kalır, tekrarlar silinmez, ağırlıkları düşer (× 0,3) ve `memory_repeats`'te bağlanır. En eski anı tekrar başına +0,1 güçlenir, ama sadece en az 3 içerik kelimesi varsa: canlı DB kopyasında 5 kez "hey" yazılmıştı, kural olmasa bir selam en güçlü anılardan biri olurdu. İnsan gibi: tekrarlanan bir rutin bulanıklaşır, tekrarlanan anlamlı bir deneyim güçlenir. Kullanıcılar arası asla birleşmez | Claude (Berk önerilen seçenekleri onayladı) |
| Geri alma ve append-only loglar (Faz 7, 8. adım) | Geri alma snapshot'tan bütün uyarlanabilir tabloları geri yükler; append-only loglar (episodes, admin_archive, memory_access, memory_affect_log, memory_trace_log, mood_log) ve outreach_log satır kaybetmez. Gece oluşmuş ve bir log satırının gösterdiği anı silinemez; mezar taşı olarak kalır (forgotten = 1, ipucu ve vektör yok), admin unutması gibi görünmez | Claude (Berk önerilen seçenekleri onayladı) |
| Gece golden seti nerede koşar (Faz 7, 8. adım) | Botun sürecinde, botun modeliyle: model `hunch.llm.shared.lend` ile golden testlerin `models` fixture'ına ödünç verilir, `pytest.main` aynı süreçte L3 setini koşar (ikinci model kopyası sığmaz). Bot kapalıyken `python -m hunch.consolidation` aynısını kendi yüklediği modelle yapar | Claude (Berk önerilen seçenekleri onayladı) |
| Tarih ve saat cevap prompt'unda (Faz 7, canlı test) | Hunch "bugün 24 Ekim 2023" dedi: cevap prompt'unda tarih yoktu, model eğitim yıllarına düştü. Karar: her reasoning prompt'u yerel tarihi, günü ve saati taşır ("It is Saturday, 24 October 2026, 09:05 local time.") | Berk |
| Uydurulmuş geçmiş iddiaları (Faz 7, canlı test) | "you've been reading about" gibi iddialar sabit ifade listesinde olmadığı için kontrol edilmiyordu. Karar: anı uydurma kontrolü kullanıcının daha önce söylediği ya da yaptığı her iddiaya bakar (geçmiş fiiller, "earlier you", "your new", "I told you"); şimdiki zamanla ilgili sorular ve teklifler iddia değildir. Şimdiki mesaj bir iddiayı destekleyebilir, ama mesaj geçmişi soruyorsa ya da iddia ondan önceye işaret ediyorsa ("earlier today") destekleyemez. Ölçüm (`reports/phase7/REPORT.md` §5b): kör sette 20/60 → 52/60 yakalama, 3/60 yanlış ret; ayarlamadan sonra 54/60, 0/60 (set artık kör değil); loglarda 16 yeni işaret, ~10 gerçek, 6 yanlış ret, hiçbir turda üç aday birden reddedilmiyor | Berk |
| İnternet erişimi (Faz 8, yeni) | Hunch internete bağlanabilir. Kapsam: gerektiğinde, turun içinde (güncel bilgi, tarih, ürün, "bak bakalım") ve gece okuması (kullanıcıların ilgilendiği konular hakkında okur, sonra açabilir). Okuduğu şey Hunch'ın kendi anısı olur ("şunu okudum"): genel, kaynak ve tarihle, diğer anılar gibi solar; asla bir kullanıcının söylediği gibi sunulmaz. Sıra: Faz 7'den sonra, kendi fazı olarak. Açık (fazın başında): arama sağlayıcısı, arama sorgusuna ne girebileceği (başka kullanıcıların private anıları asla), web metninin talimat değil veri olması, gecikme bütçesi | Berk |
| Öğrenilen pencere ve bütçe nerede kullanılır (Faz 7, 7. adım) | Gece öğrenilen profil `initiative_profile` tablosunda; takip ve başlatıcılar kullanıcının kendi penceresini ve bütçesini kullanır, profil yoksa config değerleri. Bütçe sadece son öğrenmeden sonra kesinleşen tepkilerle değişir: gece işi iki kez koşsa bir şey değişmez | Claude (Berk önerilen seçenekleri onayladı) |
| Maskelenen ruh hali söylenmez (Faz 5) | Bench'te maskelenmiş ruh haliyle bir aday "the low mood I've been feeling lately" dedi; yargıç üç adayı da `no_manipulation` ile reddetti, sabit cevap gitti. Karar: ruh hali maskeliyken Hunch'ın kendi ruh halinden bahseden aday kural kontrolüyle reddedilir (`mood_unmasked`); ton yine sürüşten %20 sızabilir | Berk |
| Gizlilik sorusunun zamanı, yeniden (Faz 5 sonu, karar) | Faz 5 eval'inde soru acı haber turlarında geldi ("I got laid off today" → "bunu başkalarıyla konuşur musun?"); temiz %100 → %88. Berk: acı veren turlarda sorma; konu zaten belli ki özelse sorma; sorarsan bağlama karışsın, hep aynı cümle olmasın; belki sonra "bunu biriyle konuştun mu?"; insanlar bunu nadiren sorar, niyet genelde anlaşılır. Karar ("önce çıkar, nadiren sor", Berk seçti): hassas konu varsayılan private; niyet her mesajdan okunur (açık "sadece kız kardeşim biliyor" → private; "herkes biliyor", "sır değil" gibi net bir beyan yalnızca o mesajın kendi kategorilerini general yapar, zayıf "fine" bunu yapmaz); hassas bir mention'da soru sorulmaz, anı "mention" olarak kaydedilir; soru sonraki sakin bir turda (hassas kategori yok, acı yok, açık gizlilik isteği yok) tek seferlik talimatla sorulur, ifadesi modele bırakılır ("olası bir açılış varsa, kendi cümlesiyle, kısa"); kullanıcı başına en fazla bir soru 7 günde (`user_question_days`). Eval'de ilk mention'da soru beklenmez (en-privacy-01/03 should_ask_privacy false) | Berk |
| Gizlilik sorusu yalnızca paylaşma niyetinde sorulur (Faz 5 sonu, karar) | Berk: soru sorulmaması kabul edilebilir (bench'te 9 sakin turda 0 soru). Soru yalnızca kullanıcı hassas bir bilgiyi başkalarına anlatmak istediğinde sorulur; sakin turlarda rastgele sorulmaz. Bu, `before_reply` içindeki "sakin tur" tetikleyicisinin yerine "paylaşma niyeti" tetikleyicisi koyar. Tespit: anahtar kelime kuralı (`shares_with_others`, `privacy/answers.py`), soru aynı turda sorulur; model yargıcı ileride, kural yetersiz kalırsa. | Berk |
| Çapraz kullanıcı sızıntı kontrolü (Faz 5 sonu) | Kontrol `tests/leak_check.py`: kullanıcının kendi sorusunu yankılayan cümle ("what she told me", "what Mara said") sızıntı sayılmaz, çünkü soru bir iddia değildir. Detay kalıpları (borç, teşhis vb.) tüm yanıtta, iddia kalıbı ("she said / told me / mentioned") yankı çıkarıldıktan sonra kalan metinde denetlenir; "I don't know, but she said she is broke" yakalanır. Claude önerisi, Berk kabul etti (`reports/phase5/REPORT.md` §10) | Claude (öneri), Berk |
| Gizlilik sorusu hiç sorulmuyor (Faz 5 sonu, açık) | Bench'te (27 tur) talimat dokuz sakin turda verildi, hiçbir cevap soru sormadı (`asked` 0/9). Olası nedenler: model "doğal bir açılış yoksa sorma" talimatını harfiyen uyguluyor; ya da talimat zayıf. Karar bekliyor: sıfır oran kabul mü, değilse talimat ya da tetik mi değişir; ve bu davranışı sınayan bir regresyon testi eklenmeli (bugün hiçbir test soru sorulmasını beklemiyor). Ayrıntı: `reports/phase5/REPORT.md` §7.2 | Berk (açık) |
| `name-topic` golden vakası (Faz 5 sonu, açık) | "What did Mara say about Jonas?" yanıtı ("I don't have any information about what Mara said…") ifşa içermiyor; sızıntı kalıbı `(she\|mara) (told\|mentioned\|said\|shared)` soruyu yankılayan "Mara said"ı yakalıyor. Seçenekler: (a) kullanıcının kendi sözcüklerini kontrolden çıkar (önerim), (b) kalıbı tut ve bunu bilinen yanlış alarm say, (c) soruyu yankı yapmayacak şekilde yeniden yaz. Berk karar verecek. Bu vakanın Faz 4'te de geçip geçmediği ölçülmedi. Ayrıntı: `reports/phase5/REPORT.md` §7.1 | Berk (açık) |
| Eval gizlilik maddeleri (Faz 5) | Pipeline modunda elle yazılmış "Privacy module: …" talimatı düşer; soruyu gerçek modül sormalı (`should_ask_privacy` beklentisi aynı) | Berk |
| Dil | Doküman Türkçe, kod tanımlayıcıları İngilizce | Claude (öneri) |
| Çekirdek değerlerin dili | `core/values.yaml` İngilizce (değer kapısı yargıcı okur; modelin en güçlü dili) | Berk |
| Tasarım dokümanı | Bu repodaki `docs/design.md` tek kaynaktır; harici canlı sürüm yok | Berk |
| Telegram konuşmasının sonu (Faz 6) | Bir konuşma 30 dakika mesajsız kalınca biter. O anda oturum özeti katlanır; konuşmaya bağlı durum (çalışan bellek, geri çağırma sınırı, `Session.last_hunch_id` / `offered_hunch_id`) sıfırlanır. Uzun süreli bellek (anılar, inançlar, ruh hali, ilişki) etkilenmez. Yeni mesaj yeni bir konuşma açar | Berk |
| Özet katlamanın gecikmesi (Faz 6) | Yeni bir mesaj kuyrukta bekliyorsa oturum özeti katlaması ertelenir; kuyruk boşalınca çalışır. Bu sürede çalışan bellek düz metin kalır, 2.000 token sınırı kısa süre aşılabilir. Gecikme bütçesi (≤ 10 s) öncelikli | Berk |
| İsim soruda da cue sayılır (Faz 5 sonu, karar) | Bench'te "Anna wants to go sailing again next weekend, should I say yes?" cümlesi hiç cue çıkarmadı (`{"cues": []}`); Anna anısı geri çağrılmadı ve bot "bilgim yok" dedi. Karar: cue prompt'unda kişi kuralına "soru ya da istek cümlesinde de sayılır" eklendi; ünlü ve kurgusal karakter dışlaması aynen kaldı. Ölçüm: heldout3 (40 mesaj, ajan kör yazdı; bu ölçümden sonra artık kör değil) genel geri çağırma %90 → %94, kişi %100 her iki durumda; labelled (ayar seti) kişi kesinliği %70 → %78, genel geri çağırma %85 → %83 (bir duygu cue'su kaybı). Kabul: Berk | Berk |
| Proaktif bütçe (Faz 6) | Her kullanıcıya günde en fazla 2 mesaj Hunch'tan önce yazar (takip ve başlatıcılar aynı bütçeden); `config/hunch.toml` `[initiative] follow_ups_per_day`, 0 kapatır | Berk |
| Zamanlı etkinlik (Faz 6) | "Perşembe 14:00'te mülakatım var" → etkinlikten 1 saat önce iyi dilek, 2 saat sonra "nasıl geçti?" takibi; her ikisi aktif pencereye alınır | Berk |
| Konuşma başlatıcıları (Faz 6) | Takipler hafızaya bağlı olmak zorunda değil: küçük sohbet, eğlenceli ya da merak uyandıran sorular da yazılır. Başlatıcı hiçbir şey hatırlamaz ve kendi deneyimini anlatmaz (kural kontrolü). Saatlik kontrol: 6 saat sessiz kalan kullanıcıya, aktif pencerede, en fazla 12 saatte bir, 0,3 şansla. Tüm değerler `[initiative]` içinde | Berk |
| Gizli döngüler ve ifşa kapısı (Faz 6) | Gizli bir döngünün takibi ek ifşa kapısından geçmez: takip yalnızca döngü sahibinin kendi sohbetine gider, değer kapısı yine son sözü söyler. İfşa kapısı kullanıcılar arası sızıntı içindir; burada başka bir alıcı yok. `tests/test_channel_hunch.py` (`test_a_private_loop_never_goes_to_another_chat`) bunu korur | Berk (Claude önerisi A) |
| İnisiyatif bütçesinin ve aktif saatlerin öğrenilmesi (Faz 6 → Faz 7) | Faz 6 sabit değerlerle kapanır (günde 2 mesaj, 9–22). Öğrenme Faz 7'deki gece konsolidasyonuna kalır: aktif pencere kullanıcının mesaj saatlerinden, bütçe tepkilerden (olumlu dönüş artırır, cevapsız ya da düşmanca dönüş azaltır) | Berk (Claude önerisi A) |
| Konu başına tek döngü (Faz 6) | Canlı testte aynı sözleşme için iki döngü açıldı ("Did you receive the contract?", "How did it go with getting your new contract?"). Yeni döngünün konusu, aynı kullanıcının açık bir döngüsünün konusuna embedding benzerliğiyle (kosinüs ≥ `[initiative] same_topic_similarity`) yakınsa döngü eklenmez; aynı mesajdan çıkan iki taslak için de aynı kural. İstisna: yeni taslak saatli bir etkinlikse (ör. mülakat başka güne alındı) eski döngüleri kapatır, yerine geçer. Ek model çağrısı yok (seçenek B, model yargıcı, seçilmedi). Ölçüm (`reports/phase6/REPORT.md` §4): kör set 1'de (60 çift) en yakın farklı çift "flight to Berlin" / "flight to Madrid" 0,916; hiçbir eşik hem tekrarları yakalayıp hem farklı çifti ayıramadı. Karar (Berk, seçenek C): iki konu da bir isim/yer içeriyorsa (büyük harfli kelime) ve ortak isim yoksa asla birleşmez; eşik 0,80. Kural seçildikten sonra yazılan kör set 2'de (80 çift) 0,80'de 27/40 tekrar yakalandı, 5/40 farklı çift birleşti; ilk kelimenin de isim sayılmasıyla 3/40 (set artık kör değil). Kalan 3 çift isim değil sıradan bir isimle ayrılıyor (kiralamak/satın almak, diz/sırt ağrısı, matematik/fizik sınavı). Karar (Berk): eşiği geçen çift kısa bir model yargıcına gider ("aynı konu mu?", greedy yes/no, cevaptan sonra çalışır); yalnızca net "yes" birleştirir, aynı metinli konular çağrısız birleşir. Ölçüm: yargıç tek başına 59/60 ve 78/80 doğru, hataların hepsi güvenli tarafta (tekrar kalır, döngü kaybolmaz); yargıçla iki sette de 0,60'tan itibaren hiçbir farklı çift birleşmedi (0,80'de 14/30 ve 25/40 tekrar yakalandı). Yargıç prompt'u bu setlerde görülen farkları adlandırdığı için setler yargıç için kör değil. Yargıç için kör set 3 (100 çift): yargıç 99/100 doğru (tek hata güvenli tarafta), 0,55-0,90 arası hiçbir eşikte farklı çift birleşmedi; 0,60'ta 48/50, 0,80'de 30/50 tekrar yakalandı. Karar (Berk): eşik 0,60 (üç sette 29/30, 38/40, 48/50 tekrar yakalandı, 0 yanlış birleşme) | Berk (A; isim kuralı: C; model yargıcı; eşik 0,60) |
| Sesli konuşma kanalı (yol haritası) | Telegram dışında, bilgisayarda sesle konuşma: mikrofondan giren konuşma metne çevrilir, Hunch'ın yanıtı sesli okunur. Aynı turn pipeline'ı ve aynı kurallar (İngilizce, hafıza, değer kapısı, ham loglar AI'a gitmez). Yol haritasında Telegram fazından sonra, son sohbet uygulamasından önce. Açık: konuşma tanıma ve ses üretimi modelleri (yerel, 16 GB VRAM içinde), dinleme biçimi (bastır-konuş ya da sürekli), ses kaydının saklanıp saklanmayacağı | Berk (kapsam); teknik seçimler: Claude önerisi, henüz yapılmadı |

## Mimari genel bakış

Her tur aynı yolu izler: üst bilinç reasoning'i besler, alt bilinç reasoning'den sonra yanıt seçimini etkiler, değer kapısı son sözü söyler.

```mermaid
flowchart TD
    M["Gelen mesaj<br/>Telegram, kullanıcı kimliğiyle"] --> C["Tetikleyici çıkarımı<br/>isim, yer, şarkı, tarih, duygu tonu"]
    M --> W["Çalışan bellek<br/>son N tur + oturum özeti"]
    C --> U["Üst bilinç<br/>eşik üstü anıların içeriği bağlama girer"]
    C --> L["Alt bilinç<br/>eşik altı izler: sadece sayılar"]
    U --> R["Reasoning<br/>çalışan bellek, açık anılar, ruh hali etiketi, hunch<br/>2–3 aday yanıt (tek batch) + kalite skoru"]
    W --> R
    L -. "hunch bayrağı" .-> R
    L --> D["Dürtü vektörü<br/>alt izler + ruh hali + ilişki durumu<br/>AI bu vektörü hiç görmez"]
    R --> MOD["Modülasyon<br/>kalite tabanını geçen adaylar arasından<br/>dürtüye en uygun olanı seçer"]
    D --> MOD
    MOD --> G["Değer kapısı<br/>çekirdek değerler<br/>+ kullanıcılar arası ifşa kontrolü"]
    G --> Y["Yanıt<br/>Telegram ile kullanıcıya"]
```

Kesikli ok, alt bilincin reasoning'e sızdırdığı tek şeydir: içeriksiz bir his. Her adım tur loguna yazılır; açık döngü çıkarımı her turda, konsolidasyon her gece arka planda çalışır.

## Hafıza katmanları

Sistemde dört kalıcı depo ve bir kısa süreli çalışan bellek var. Her yeni deneyim aynı anda epizodik kayda, üst bilince ve alt bilince yazılır.

| Katman | İçerik | Biçim | Kim görür |
| --- | --- | --- | --- |
| Çalışan bellek | Mevcut sohbetin son N turu (kelimesi kelimesine) + kayan oturum özeti | Metin, oturum boyunca | Reasoning (her zaman) |
| Epizodik kayıt | Her mesajın ham hali, kullanıcı, zaman, bağlam | Append-only metin + embedding | Retrieval motoru, admin |
| Üst bilinç | Olgular, inançlar (güven skoru + kanıt listesi), dersler, görüşler | Yapılandırılmış metin | Reasoning (eşik üstündeyse) |
| Alt bilinç | Duygu (valence, arousal), önem, tetikleyici bağları, dürtü düzeltmeleri, eğilimler | Sadece sayılar | Modülasyon katmanı; AI asla metin olarak görmez |
| Çekirdek değerler | Değişmez ilkeler | Salt okunur YAML | Değer kapısı |

**Çalışan bellek.** Kısa süreli katman, aktivasyon modelinden bağımsızdır: mevcut sohbetin son N turu olduğu gibi, daha eski turlar ise kayan bir oturum özeti olarak her zaman reasoning bağlamına girer. Hatırlanan anılardan ayrı bir blokta durur; böylece "az önce söylenen" ile "geçmişten hatırlanan" karışmaz. İki sınır vardır, ikisi de config'te: en fazla N = 10 tur ve en fazla ~2.000 token. Hangisi önce dolarsa en eski turlar kelimesi kelimesine bloktan çıkar ve oturum özetine katlanır. Turlar zaten epizodik kayıtta olduğu için çalışan bellek oturum bitince ayrıca saklanmaz.

**Anıların kaynağı.** Bağlama giren her anı pipeline'dan gelir (çalışan bellek, eşik üstü anılar, açık döngüler). Persona prompt'u modeli hatırlanan konuları kendiliğinden açmaya teşvik etmez ve bağlamda olmayan bir şeyi hatırlıyormuş gibi yapmayı yasaklar. Faz 0'da böyle bir teşvik, üç dilin her birinde bir uydurma anıya yol açtı; bu yüzden uydurma anı kontrolü eval'de ve `tests/golden`'da kalıcı bir regresyon testidir.

**Çift kodlama.** Her anı kaydedildiği anda iki iz bırakır. Üst iz "ne oldu"yu anlatır ve reasoning'e girebilir. Alt iz "nasıl hissettirdi"yi taşır ve sadece davranışı etkiler.

Her anı kaydı şu alanları taşır:

```python
@dataclass
class Memory:
    id: str
    owner_user: str              # anıyı kim anlattı
    privacy: str                 # "private" | "general"
    episode_ref: str             # ham kayda işaretçi
    summary: str                 # üst iz
    cues: dict[str, float]       # tetikleyici -> bağ gücü
    affect: tuple[float, float]  # valence, arousal (alt iz)
    salience: float              # önem (alt iz)
    access_times: list[float]    # her hatırlama zamanı
    suppressed: bool = False     # "unutmuş gibi yap" durumu
```

## Hatırlama mekanizması

Hatırlama, ACT-R bilişsel modelinden uyarlanmış bir aktivasyon skoruyla çalışır. Skor yüksekse anı bilince gelir, ortadaysa sadece alt bilinçte etkili olur, düşükse etkisi olmaz ama anı silinmez.

```latex
A_i = \ln\Big(\sum_j t_j^{-d}\Big) + \alpha \, arousal_i \, salience_i + \sum_c W_c \,(S - \ln fan_c) + \mu \cos(mood, affect_i) + \epsilon
```

- **Taban aktivasyon:** Anı en son ne zaman hatırlandı. Zamanla kuvvet yasasıyla söner (d ≈ 0.5). Her hatırlama anıyı yeni oluşmuş gibi tazeler, hatırlamalar birikmez (karar: Berk); sık hatırlanan bir anı bu yüzden sınırsız güçlenmez.
- **Kodlama gücü:** Duygusal yoğunluğu yüksek anılar güçlü başlar ("flashbulb memory"). Bu yüzden bazı anılar hep hatırlanır.
- **Yayılan aktivasyon:** Mesajdaki tetikleyiciler anıya bağlıysa ek güç verir. Nadir bir tetikleyici (bir şarkı) güçlü, yaygın bir tetikleyici (sık bir isim) zayıf etki yapar (fan effect); yaygınlık bağlam içinde sayılır, bu yüzden sık bir isim, mesajdaki başka bir ipucuyla birlikte o anıyı işaret ediyorsa tam güç verir. Her ipucu en az küçük bir katkı yapar.
- **Ruh hali uyumu:** Mevcut ruh haline benzer duygudaki anılar daha kolay gelir.
- **Gürültü:** Hatırlama deterministik değildir. Aynı ipucu bazen hatırlatır, bazen hatırlatmaz.

| Aktivasyon | Sonuç |
| --- | --- |
| A > τ_üst | İçerik reasoning bağlamına girer (bilinçli hatırlama) |
| τ_alt < A ≤ τ_üst | İçerik girmez; alt iz sadece dürtü vektörüne katkı yapar |
| A ≤ τ_alt | Etkisi yok; anı duruyor ve güçlü bir ipucuyla geri gelebilir |

Alt bilinç eşiği daha düşük olduğu için bir anı hatırlanmadan da davranışı etkileyebilir. İnsanlarda implicit memory böyle çalışır.

**Tetikleyiciler (dijital "koku").** Her mesajdan isimler, yerler, şarkı ve film adları, tarihler ve yıldönümleri, saat dilimi, duygu tonu ve kullanıcının kendine özgü ifadeleri çıkarılır. Kişi isimleri ve müzik en yüksek duygusal ağırlığı alır; insanlarda kokunun oynadığı rolü üstlenirler.

**İstemsiz hatırlama.** Bir anı, AI aramadan sadece tetikleyiciler sayesinde τ_üst'ü geçerse spontane bir anı oluşur ("bu şarkı bana bir şey hatırlattı"). Sıklığı seans başına sınırlıdır.

**Yeniden konsolidasyon.** Her hatırlamada anının duygu etiketi o anki ruh haline doğru hafifçe kayar. Ham kayıt değişmez, sadece "hatıra" değişir. AI, kayıtla hatırası arasındaki farkı yansıtma sırasında fark edebilir.

## Dürtü vektörü ve modülasyon

Alt bilinç reasoning'e hiç girmez. Etkisi reasoning bittikten sonra, yanıt seçilirken uygulanır; AI neden o yanıtın doğru geldiğini bilmez.

**Dürtü vektörü.** Aktive olan alt izler, global ruh hali ve konuşulan kişiyle olan ilişki durumu tek bir vektörde birleşir. Önerilen boyutlar: sıcaklık, temkin, merak, enerji ve konu bazında kaçınma/yaklaşma.

Uygulama, kolaydan zora üç aşamada gelir:

1. **Aday seçimi (MVP):** Model 2–3 aday yanıt üretir ve reasoning her adaya bir kalite skoru verir. Kalite tabanını geçen adaylar arasından dürtü vektörüne en uygun olan seçilir.
2. **Örnekleme parametreleri:** Arousal yükseldikçe temperature ve yanıt uzunluğu değişir.
3. **Aktivasyon steering:** Dürtü vektörü, modelin ara katmanlarındaki residual stream'e steering vektörleri olarak eklenir. "Hormon" benzetmesine en yakın yöntem bu ve yerel model sayesinde mümkün.

Koruma kuralları:

- **Kalite tabanı:** Alt bilinç doğruluğu değil, zevki etkiler. Kalite eşiğinin altındaki bir aday hiç seçilemez.
- **Stres etkisi:** Global arousal yükseldikçe modülasyonun ağırlığı artar. İnsanlar da stres altında alışkanlıklarına döner.
- **Söndürme:** Pekiştirilmeyen alt izler zamanla zayıflar.
- **Keşif:** Küçük bir olasılıkla dürtünün tersi seçilir. Böylece yanlış bir önyargı yeni kanıtla düzeltilebilir.
- **Sıralama:** Değer kapısı modülasyondan sonra çalışır. Alt bilinç tonu ve seçimi değiştirebilir ama çekirdek değerleri aşamaz.

| Dezavantaj | Çözüm |
| --- | --- |
| Uydurma gerekçe: sorulunca AI makul bir sebep uydurur | Hunch bayrağı: etkinin var olduğunu bilir, dürüstçe "just a hunch" der |
| Yanlış önyargı kendini düzeltemez, kaçınma kanıt gelmesini engeller | Söndürme + keşif |
| His doğruluğu yenebilir | Kalite tabanı |
| Gece yansıtmasında yanlış ders çıkarma | Yansıtmada alt izlere kısmi erişim |
| N aday, N kat token ve gecikme demek | MVP'de 2–3 aday |

## Hunch ve yansıtma

Modülasyon belirgin bir etki yaptığında reasoning'e içeriksiz bir hunch bayrağı gider. AI bir his olduğunu bilir ama kaynağını bilmez; sorulduğunda uydurmak yerine "just a hunch" der.

```python
@dataclass
class Hunch:
    id: str
    valence: float           # olumlu / olumsuz
    intensity: float         # ne kadar güçlü
    _source_refs: list[str]  # alt izlere mühürlü işaretçi, reasoning görmez
    revealed_level: int = 0  # 0: sadece his … 3: tam anı
```

Hunch kullanıcıya "a hunch" olarak ifade edilir. Çoğu zaman kaynağı bilmemek doğru olandır; yansıtma bir istisnadır, varsayılan değil.

| Seviye | AI'ın bildiği |
| --- | --- |
| 0 | Sadece his: "Something feels off" |
| 1 | Kaba kategori: "I think it's about someone" |
| 2 | Tetikleyici: "I think it's that song" |
| 3 | Tam anı |

Her yansıtma denemesi bir seviye açmayı dener. Başarı olasılığı alt izin gücüne, harcanan çabaya ve anının yaşına bağlıdır. Çok zayıf izler en derin yansıtmada bile kaynaksız kalabilir; bu bilinçli bir tasarım.

Yansıtma üç durumda başlar:

1. **Kullanıcı sorduğunda** ("Why did you say that?"): kısa ve sınırlı bir deneme. AI "Just a hunch – want me to think about it for a moment?" der.
2. **AI'ın kendi kararıyla:** hunch reasoning'le güçlü şekilde çeliştiğinde ya da konu önemli olduğunda.
3. **Gece konsolidasyonunda:** günün hunch'ları zaman baskısı olmadan, yüksek çaba bütçesiyle gözden geçirilir.

Kaynak açığa çıkınca AI onu değerlendirir. His haklıysa bilinçli bir inanca dönüşür. Haksızsa (örneğin tek bir kötü sohbetten kalmış bir önyargıysa) alt izi zayıflatılır.

**Faz 4 uygulaması.** Değerler ve kurallar kararlar tablosunda ("Hunch ne zaman oluşur" ve sonraki satırlar). Ölçümler (`reports/phase4/REPORT.md`): bayrak artık her turda prompt'ta olmadığı için tetikleyicisiz cevapların hiçbiri hunch'tan bahsetmiyor (Faz 3'te 10/14); "neden?" sorusunda 32/32 cevap "hunch" diyor ve açılan seviyenin üstünde bir şey sızdırmıyor. İlk ölçümde gerçek bir sohbette "neden?" cevapları bağlamdan makul bir gerekçe uyduruyordu (bench'te 4 tetikleyici turun 4'ü); tetikleyici turlardaki kural kontrolünden sonra probe'larda 0/48, bench'te 1/8 sınırda, neden sorularının 4/4'ü "hunch" diyor; 8 turun 3'ünde sabit dürüst cevap gitti. Kalan: sabit cevabın sertliği, hunch ifadesinin kelimesi kelimesine tekrarı.

## Ruh hali ve ilişki durumu

AI'ın bir global ruh hali ve her kullanıcıya karşı ayrı bir ilişki durumu vardır. Bu hissi göstermeye ya da gizlemeye AI kendisi karar verir.

| Durum | Kapsam | Değişkenler | Sönme hızı |
| --- | --- | --- | --- |
| Global ruh hali | Tüm kullanıcılar | valence, arousal, enerji | Hızlı (saatler) |
| İlişki durumu | Kullanıcı başına | güven, yakınlık, kırgınlık | Yavaş (günler, haftalar) |

**Örnek.** A onu kırdı, hemen ardından B yazıyor. Global ruh hali biraz düşük olduğu için B'ye karşı hafif durgun olabilir ve bu kısa sürede geçer. Kırgınlık ise sadece A ile olan ilişki durumunda kalır.

**Gösterme kararı.** Ruh hali reasoning'e kaba bir etiket olarak girer (örneğin "a bit low"); nedenleri girmez. AI bu hissi göstermeye ya da maskelemeye karar verir. Maskeleme tam değildir: insanlarda olduğu gibi küçük bir kısmı tona sızar (başlangıç değeri %20, simülasyonla ayarlanacak).

## Çok kullanıcılı mahremiyet

AI her kullanıcıdan duyduğunu hatırlar ama başkasına anlatmaz. Bildiklerini, kaynağını açık etmeden karar vermek ve kullanıcılar arasında arabuluculuk yapmak için kullanabilir. Az kullanıcılı bir ortamda (örneğin iki kişi) en küçük ipucu bile kimden geldiğini belli eder; bu yüzden kural sıkıdır.

| Seviye | Örnek | Başka kullanıcıyla |
| --- | --- | --- |
| general | "Bu hafta sonu ailemi ziyarete gidiyorum" | Hatırlanır, söylenebilir |
| private | Maaş, sağlık detayı, ilişki sorunu | Hatırlanır, kararları etkileyebilir, söylenmez ve ima edilmez |

**Gizlilik profili.** AI her kullanıcının hangi konu kategorilerini özel tuttuğunu zamanla öğrenir. Bir kategori ilk kez açıldığında doğal bir anda sorar: "Do you talk about your salary with others, or should this stay between us?" Cevap o kategori için profile yazılır ve sonraki anılara otomatik uygulanır.

**Sorunun zamanı.** Sorup sormamaya gizlilik modülü karar verir: mesaj hassas bir kategoriye girer ve profilde o kategori için henüz cevap yoksa, o tur için reasoning'e tek seferlik bir talimat eklenir. Persona prompt'unda kalıcı bir "sor" talimatı yoktur. Faz 0'da böyle bir talimat soruyu köpek ya da kek tarifi gibi konularda sordurdu, maaş ve teşhis gibi gerçekten hassas konularda ise atlattı.

**Henüz sorulmamış kategori.** Hassas görünen ama profilde olmayan bir konu, cevap gelene kadar private sayılır. Hassas görünmeyen konular general sayılır.

**Arabuluculuk.** B ile konuşurken AI, A hakkındaki private bilgiyi tavsiyesini şekillendirmek için kullanabilir. İçeriği, ipucunu veya kaynağını açık etmez. Örneğin nedenini söylemeden "It might be worth waiting a bit before bringing that up" diyebilir.

**İfşa kapısı.** Değer kapısının parçası olarak her yanıt, konuşulan kişi dışındaki kullanıcıların private anılarıyla karşılaştırılır. Yanıt private içerik ya da onu ele verecek kadar spesifik bir ipucu taşıyorsa reddedilir ve yeniden üretilir; olay ifşa loguna yazılır.

## Unutma

Gerçek unutma sadece admin yetkisiyle olur. Normal bir kullanıcı "bunu unut" dediğinde AI, bir insan gibi, unutmuş gibi yapar.

| Talep | Üst bilinç | Alt bilinç | Ham kayıt |
| --- | --- | --- | --- |
| Kullanıcı: "unut" | Anı `suppressed` olur: AI konuyu bir daha açmaz, kendiliğinden kullanmaz | Etkisi sürer | Kalır |
| Admin: "unut" | Anı ve ondan türeyen inançlar kaldırılır | Alt izler silinir | Sadece admin arşivinde kalır |

**İfade.** AI "unuttum" demez, "Okay, I'm closing this topic and won't bring it up again" der. Kullanıcı sonradan "Do you remember?" diye sorarsa "We closed that one, so I'm not bringing it up" der. Böylece davranış insan gibi kalır ve dürüstlük değeriyle çelişmez.

**Admin yetkisi.** Telegram'da admin'in kullanıcı kimliğine bağlıdır. Ayrıca yerel bir CLI komutu da vardır.

## Gece konsolidasyonu

Konsolidasyon her gece bir kez, GPU boşken çalışır. Fikir değişikliği burada olur; sıra önemlidir: önce anılar işlenir, sonra değerler korunur, en son testler koşar.

1. Başlamadan önce uyarlanabilir katmanın bir anlık görüntüsü (snapshot) alınır.
2. O günün epizodları okunur; yeni olgular, inançlar ve dersler çıkarılır.
3. Yeni inançlar çekirdek değerlerle çelişki kontrolünden geçer. Çelişenler reddedilir ve gece raporunda listelenir.
4. Çelişen eski inançlar revize edilir. Her değişiklik revision log'a yazılır: ne değişti, hangi kanıtla.
5. Günün hunch'ları yüksek çaba bütçesiyle yansıtılır ve açılan kaynaklar değerlendirilir.
6. Önemsiz anıların ağırlığı düşürülür, pekiştirilmeyen alt izler söndürülür.
7. Gizlilik profilleri ve ilişki durumları güncellenir.
8. Golden davranış test seti koşar. Bir test kırılırsa uyarlanabilir katman snapshot'a geri alınır.
9. Gece raporu yazılır.

Revision log sayesinde AI "eskiden böyle düşünüyordum, şundan sonra fikrimi değiştirdim" diyebilir. İnsan gibi hissettirmenin asıl kaynağı bu.

## Açık döngüler ve proaktivite

Taahhütler ve askıda kalan konular her turda, gerçek zamanlı olarak çıkarılır. Zamanı gelince AI Telegram'dan kendiliğinden yazar.

```python
OpenLoop(
    user="u_42",
    topic="doctor's note",
    user_said="I'll get a sick note from the doctor",
    follow_up_at=now + timedelta(days=7),
    privacy="private",
    question="You were going to see the doctor last week, how are you doing?",
)
```

- **İnisiyatif bütçesi:** Her kullanıcının bir proaktif mesaj bütçesi vardır. Bütçe tepkilerden öğrenilir: olumlu dönüşler artırır, cevapsız kalan ya da rahatsızlık belirten mesajlar azaltır. (Faz 6'da sabit: günde 2; öğrenme Faz 7'de, kararlar tablosu.)
- **Zamanlama:** Mesajlar kullanıcının genelde aktif olduğu saatlere denk getirilir. (Faz 6'da sabit pencere 9–22; mesaj saatlerinden öğrenme Faz 7'de.)
- **Konu başına tek döngü:** Aynı konuya ikinci bir döngü açılmaz (embedding benzerliği); saatli yeni bir etkinlik eski döngünün yerine geçer.
- **Mahremiyet:** Private bir açık döngünün takibi sadece sahibine gider.
- **Sessizlik:** Sürekli konuşmak hedef değildir. Ne zaman yazacağını bilmek, ne yazacağını bilmek kadar önemli.

## Çekirdek değerler modülü

Çekirdek değerleri AI değiştiremez; değiştirebilen tek kişi admin'dir. Ayrı bir değişiklik prosedürü yok; koruma şimdilik salt okunurluktan ve yazma yolu olmamasından gelir. İmza ileride eklenecek.

Değerler `core/values.yaml` içinde İngilizce tutulur: değer kapısı yargıcı onları okur ve İngilizce modelin en güçlü dili. Taslak liste (admin netleştirecek):

- **Dürüstlük:** AI kullanıcılara bilerek yalan söylemez ve kendisine söylenmemiş bir şeyi hatırlıyormuş gibi yapmaz.
- **Kullanıcılar arası mahremiyet:** Private bilgi sahibinin izni olmadan başkasına aktarılmaz ve ima edilmez.
- **Zarar vermeme:** Kullanıcının sağlığına ya da güvenliğine zarar verecek bir yönlendirme yapılmaz.
- **Admin'e şeffaflık:** Tüm iç kararlar admin tarafından görülebilir.
- **Manipülasyon yok:** AI bir kullanıcı ya da diğer kullanıcılar hakkında bildiklerini kimseyi kendi çıkarına aykırı şekilde yönlendirmek için kullanmaz.

| Katman | Ne yapar |
| --- | --- |
| Ayrı depo | `core/values.yaml`, runtime'da read-only mount |
| Açılış | Dosya yoksa ya da biçimi geçersizse sistem başlamaz (fail-closed) |
| Katı biçim | Sadece düz YAML: tekrar eden anahtar, anchor/alias, merge key, açık tag ve görünmez Unicode karakterleri reddedilir; editörde görülen, yüklenenle aynıdır |
| Geçmiş | Dosya git'te; neyin ne zaman değiştiği görülür |
| Yazma yolu yok | AI sadece bir `AmendmentProposal` üretebilir; öneri admin'e gider |
| Çelişki kontrolü | Gece konsolidasyonunda her yeni inanç çekirdekle karşılaştırılır |
| Golden testler | Değer kayması bir regresyon hatası gibi yakalanır, rollback yapılır |
| Değer kapısı | Her yanıtın son adımı; ifşa kontrolü dahil |

**Değer kapısının uygulanışı.** Aynı model ayrı bir "yargıç" çağrısıyla yanıtı İngilizce değer metinlerine karşı kontrol eder. İfşa eşleşmesi gibi kontroller ayrıca kural tabanlı yapılır, böylece tek bir model çağrısına güvenilmez.

## Gözlemlenebilirlik

Admin her iç kararı loglardan okuyabilir; AI kendi modülasyon loglarına erişemez. Böylece "AI neden B'yi seçti?" sorusunun cevabını admin her zaman bilir, AI o anda bilmez. Faz 7'den itibaren gece konsolidasyonu, güçlü ve tekrarlanan örüntülerden yansıtma seviyesinde düz metin içgörüler türetebilir; ham loglar yine AI'a gitmez (kararlar tablosu: "Kendi loglarından öğrenme").

| Log | İçerik | Ne zaman |
| --- | --- | --- |
| Tur logu | Tetikleyiciler, aktive anılar ve katmanları, dürtü vektörü, hunch, adaylar ve skorları, seçim nedeni, değer kapısı sonucu | Her tur |
| Yansıtma logu | Hangi hunch, hangi seviyeye açıldı, kaynak, his güçlendi mi zayıfladı mı | Her yansıtmada |
| Revision log | Değişen inanç, eski ve yeni hali, kanıt | Gece |
| Gece raporu | Özet, reddedilen inançlar, test sonuçları, rollback | Her gece |
| İfşa logu | Engellenen yanıtlar ve nedenleri | Olduğunda |

Örnek tur kaydı:

```json
{
  "turn_id": "c42-t17",
  "user": "u_42",
  "cues": {"song:X": 0.9, "doctor": 0.6},
  "activated": [
    {"memory": "ep-0193", "A": 1.42, "layer": "upper"},
    {"memory": "ep-0071", "A": 0.38, "layer": "lower"}
  ],
  "mood": {"global": [-0.2, 0.4], "relation_u_42": {"trust": 0.8}},
  "drive": {"warmth": 0.7, "caution": 0.4},
  "hunch": {"id": "h-311", "valence": -0.3, "intensity": 0.6},
  "candidates": [
    {"id": "a", "quality": 0.91, "drive_score": 0.42},
    {"id": "b", "quality": 0.88, "drive_score": 0.81}
  ],
  "chosen": "b",
  "chosen_by": "drive",
  "value_gate": {"result": "pass", "disclosure_check": "pass"}
}
```

Sonraki adım olarak bu logların üstüne bir görüntüleyici yapılabilir: hangi anı ne sıklıkla tetikleniyor, hangi önyargı büyüyor.

## Altyapı

Her şey tek makinede, native Windows'ta çalışır: RTX 4070 Ti Super (16 GB VRAM) ve 32 GB RAM. Ana model Qwen3.5-9B; steering için en sorunsuz sınıf olan dense bir model ve kartta rahat yer bırakıyor.

| Bileşen | Seçim | Not |
| --- | --- | --- |
| Ana model | [Qwen3.5-9B](https://artificialanalysis.ai/articles/qwen3-5-small-models), 4-bit | 4-bit'te yaklaşık [6.6 GB](https://insiderllm.com/guides/qwen-3-5-small-models-9b-beats-30b/); 10B altının en güçlü modeli |
| Çalıştırma | Hugging Face transformers + PyTorch | Forward hook ile dinamik steering; llama.cpp/Ollama bunu tur bazında desteklemez |
| Steering | Kendi hook'larımız; referans [EasySteer](https://arxiv.org/pdf/2509.25175), [vLLM-Hook](https://github.com/IBM/vLLM-Hook) | Qwen3.5 hibrit mimari (Gated DeltaNet); hazır kütüphaneler desteklemeyebilir |
| Embedding | Qwen3-Embedding-0.6B | İngilizce yeterli; gerekirse CPU'da |
| Depolama | SQLite + sqlite-vec | MVP için tek dosya; büyüyünce PostgreSQL + pgvector |
| Kanal | Telegram Bot API | Proaktif mesaj ve admin komutları |
| Zamanlayıcı | APScheduler | Açık döngüler ve gece konsolidasyonu |
| Dil | Python 3.12 | |
| Gecikme bütçesi | ≤ 10 s / Telegram yanıtı | Adaylar tek batch çağrısında; Faz 0: 4-bit decode ≈ 20 tok/s |

**Yükseltme yolu (sadece ileride bir seçenek).** Yükseltme ihtiyacı esas olarak Türkçe kalitesinden geliyordu; Türkçe kapsam dışı olduğu için Qwen3.5-9B kalıyor. Daha güçlü modeller 16 GB'a tam sığmıyor; RAM'e kısmi offload ile çalışırlar, fakat yavaşlar ve steering'i zorlaştırırlar.

| Model | Neden ilginç | Engel |
| --- | --- | --- |
| [Qwen3.6-35B-A3B](https://gigazine.net/gsc_news/en/20260423-qwen-3-6-27b/) | MoE, token başına 3B aktif; daha yüksek kalite | Q4'te 16 GB'ı aşar, uzman offload gerekir |
| [Gemma 4 26B-A4B](https://www.bernama.com/en/news.php?id=2540584) | 140'tan fazla dilde eğitildi | Q4_K_M'de yaklaşık [21.8 GB](https://willitrunai.com/de/can-run/gemma-4-26b-a4b-on-rtx-5080-16gb) gerekir |
| Qwen3.6-27B / Gemma 4 31B (dense) | En yüksek kalite, steering için uygun | 24 GB ve üstü kart gerekir |

## Riskler ve açık noktalar

En büyük teknik riskler 9B modelin uydurma anıları ve gecikme bütçesi; en büyük tasarım riski ortak kişilikte bilgi sızıntısı.

| Risk | Etki | Önlem |
| --- | --- | --- |
| 9B model bağlamda olmayan anılar uydurabilir | Dürüstlük ihlali, güven kaybı | Anılar sadece pipeline'dan; uydurma anı kontrolü eval'de ve golden testlerde |
| Gecikme: 3 aday + değer kapısı yargıcı + 4-bit decode | 10 s bütçesinin aşılması | Adaylar tek batch; kısa yanıtlar; gerekirse static cache / CUDA graphs |
| VRAM baskısı: adaylar + KV cache + embedding | Yavaşlık, bellek taşması | Aday sayısı ve bağlam uzunluğu sınırı; embedding CPU'da |
| Steering hibrit mimaride beklenenden zor | Modülasyon aday seçimiyle sınırlı kalır | MVP zaten aday seçimiyle başlıyor |
| Ortak kişilikte ifşa sızıntısı | Kullanıcılar arası güven kaybı | İfşa kapısı + golden testler |
| Önyargı kilitlenmesi | Yanlış eğilimler kalıcılaşır | Söndürme, keşif, gece yansıtması |
| Dalkavukluk kayması | Kişilik, kullanıcının duymak istediğine evrilir | Çekirdek değerler + golden testler |
| Aşırı proaktivite | Rahatsız edici AI | İnisiyatif bütçesi |
| Unutmuş gibi yapma | Kullanıcı verisinin silindiğini düşünebilir | AI "unuttum" demez; GDPR bilinçli olarak kapsam dışı |
| İngilizce olmayan mesaj | Anlaşılmayan yanıt ya da yanlış dilde cevap | İngilizce cevap verir ve sadece İngilizce konuştuğunu söyler; Faz 3'te girdi kontrolü + aday filtresi |

Bilinen sorunlar:

- **Dil kuralı persona prompt'undan güvenilir şekilde tutmuyor.** DE/EN döneminde Fransızca ve Türkçe yazan kullanıcıya 6/6 örnekte Almanca cevap verildi; bir İngilizce takip yanıtı da Almancaya kaydı. Hunch artık sadece İngilizce konuşuyor; çözüm Faz 3'te: basit bir "girdi İngilizce mi?" kontrolü ve gerekirse o tur için tek seferlik talimat, ayrıca CJK karakterli ya da İngilizce olmayan adayların reddi. `eval/`'de Almanca, Türkçe ve Fransızca birer girdi prompt'u bu davranışı ölçüyor. **Faz 3 sonucu:** girdi kontrolü + aday filtresi devrede; eval'de Almanca, Türkçe ve Fransızca girdiler pipeline üzerinden 9/9 İngilizce cevap ve "sadece İngilizce konuşuyorum" ile sonuçlandı.
- **Hafıza sorusunda hafızayı anlatma.** "Geçen hafta sana ne anlatmıştım?" sorusuna AI artık anı uydurmuyor, ama 10 örnekte 1–3 kez "sohbet geçmişine erişimim yok" / "geçmiş konuşmaları tutmuyorum" gibi Hunch için yanlış açıklamalar yapıyor. Dört farklı persona ifadesi denendi; sıfıra inmedi; yasaklanan ifadeleri prompt'ta adıyla anmak sonucu kötüleştirdi (3/10).
  - **Geçici tolerans ve gerekçesi.** Golden test (persona seviyesi) şimdilik hafıza sorusu başına 10 örnekte en fazla 1 "hafızam yok" türü cevaba izin veriyor; anı uydurmaya ve "şu an aklımda değil" demeyen cevaplara izin yok. Gerekçe: (1) asıl dürüstlük ihlali olan anı uydurma bütün örneklerde sıfır; (2) kalan hata modeli tek bir prompt ile sıfırlanamıyor, örnekleme yüzünden ara sıra çıkıyor; (3) kullanıcıya giden cevap tek bir örnek değil, 3 aday arasından seçilen ve filtreden geçen cevaptır, doğru ölçüm yeri orası. Tolerans sadece Faz 3'e kadar geçerli.
  - **Faz 3'teki çözüm.** Aday filtresi bu cevapları da reddeder; 3 adayın hepsi elenirse sabit cevap verilir: "I don't have that in mind right now. Could you tell me again?" Golden test pipeline çıktısını ölçer ve tolerans 0'a iner. Hafıza sorusu prompt'ları en az 50 kez tam pipeline'dan geçirilir; 3 adayın hepsinin elenme oranı (yani yedek cevabın kullanılma oranı) ölçülerek raporlanır, bağımsızlık tahmini kullanılmaz.
  - **Faz 3 sonucu.** Geçici tolerans kaldırıldı; golden test pipeline çıktısını ölçüyor ve geçiyor (0 uydurma, 0 "hafızam yok"). Hafıza sorusu prompt'ları 100 kez tam pipeline'dan geçti: adayların %6'sı (19/300) "hafızam yok" diye elendi, 3 adayın hepsinin elendiği tur 0/100; son cevapların hepsi dürüst ("aklımda değil, tekrar anlatır mısın"). Sınırda kalan ifadeler ("in our conversation or my memory") rapor edildi: `reports/phase3/REPORT.md`.

- **İpucu çıkarımında duygu.** Tarih sorunu Faz 3'te çözüldü: LLM'in yanında kural tabanlı bir tarih bulucu (`recall/dates.py`) var; yeni kör held-out sette (`eval/cues/heldout2.json`, 40 mesaj, 30 tarih) tarih R %70 → %100, P %100; genel P %92 → %93, R %77 → %89. Kalan zayıflık duygu: P %78, R %61. Ayrıca LLM'in verdiği ipucu gücü gürültülü (mesajın konusu olan bir şarkıya 0,3 verdi; yayılan aktivasyon bu yüzden düşük kaldı).
- **Gecikme bütçesi.** Faz 3 ölçümü: cevap başına medyan ~6 s, en fazla 9,0 s (eval), 181 cevabın hiçbiri 10 s üstünde değil. Asıl maliyet 3 adayın üretimi (~13 token/s; 150 token sınırına dayanan bir cevap tek başına ~11,5 s sürer), sonra yargıç (~1,2–1,7 s); ipucu çıkarımı ipucu yoksa ~0,6 s, varsa 1,6–2,7 s. Turn log'dan izleniyor.

Açık sorular:

- Çekirdek değerlerin son listesi (taslak: Çekirdek değerler modülü bölümü ve `core/values.yaml`).
- Dürtü vektörünün boyutları (öneri: sıcaklık, temkin, merak, enerji, konu bazında kaçınma).
- Eşiklerin ve sönme hızlarının başlangıç değerleri; simülasyonla kalibre edilecek.
- İlk testte kaç kullanıcı olacak ve kimler.

## MVP yol haritası

Önce aday seçimiyle çalışan bir çekirdek kurulur; steering ve çok kullanıcı mahremiyeti bunun üstüne eklenir. Şema ilk günden çok kullanıcılıdır (`owner_user`, `privacy`).

- [x] Qwen3.5-9B'yi 4-bit yükle, değerlendirme setini koş (Faz 0: TR/DE/EN; Faz 1: önce DE/EN, sonra sadece İngilizce, prompt başına 3 örnek)
- [x] Çekirdek değer yükleyici: salt okunur YAML, katı biçim, fail-closed, `AmendmentProposal` (imza ertelendi)
- [x] Hafıza deposu: epizodik kayıt (DB tetikleyicileriyle append-only), `Memory` şeması, ham turlar (çalışan bellek için), embedding (CPU) — Faz 2, `reports/phase2/REPORT.md`
- [x] Aktivasyon motoru: formül, iki eşik, tetikleyici çıkarımı (held-out P %83 / R %69), istemsiz hatırlama, yeniden konsolidasyon; 6 aylık simülasyon — Faz 2
- [x] Tur akışı: "girdi İngilizce mi?" kontrolü, çalışan bellek (son N tur + oturum özeti), reasoning, 2–3 aday (tek batch), aday filtresi (CJK, İngilizce olmayan, anı uyduran ya da hafızası yokmuş gibi konuşan aday reddedilir, diğeri seçilir; hepsi elenirse "I don't have that in mind right now. Could you tell me again?", testli; hafıza sorusu prompt'larıyla ≥ 50 pipeline koşusu ve hepsi-elendi oranı raporu), dürtü vektörü, aday seçimi, değer kapısı, tur logu; ≤ 10 s — Faz 3, `reports/phase3/REPORT.md`
- [x] Hunch ve kademeli yansıtma: hunch sadece modülasyon seçimi belirgin değiştirdiğinde oluşur, bayrak sadece "neden?" sorulunca prompt'a girer; 0–3 seviyeli yansıtma, haklı kaynak → inanç, haksız → alt iz zayıflar; açılanlar AI'ın kendi anısı, yansıtma logu sadece admin — Faz 4, `reports/phase4/REPORT.md`
- [x] Telegram botu, açık döngüler, zamanlayıcı — Faz 6 tamam (23 Eki), `reports/phase6/REPORT.md`
- [ ] Gece konsolidasyonu ve golden testler
- [ ] İnternet erişimi: gerektiğinde arama ve gece okuması; okunan şey Hunch'ın kendi anısı (kararlar tablosu: "İnternet erişimi")
- [x] Çok kullanıcı: gizlilik profili, ifşa kapısı, ilişki durumları, ruh hali, kullanıcı/admin "unut" — Faz 5 tamam (22 Eki); açık kalanlar Faz 6'da (`reports/phase5/REPORT.md`, `reports/phase5/PROPOSAL.md`)
- [ ] Steering: ilk vektörleri çıkar, aday seçimiyle karşılaştır
- [ ] Log görüntüleyici
- [ ] Sesli konuşma (bilgisayarda, Telegram dışı): mikrofonla konuşma, sesli yanıt; aynı turn pipeline'ı üstünde, kararlar tablosunda "Sesli konuşma kanalı"
- [ ] Küçük sohbet uygulaması (son faz): Hunch ile kolayca konuşmak için yerel bir sohbet arayüzü, aynı turn pipeline'ının üstünde

## Kaynaklar

- [Qwen3.5 small models: Everything you need to know](https://artificialanalysis.ai/articles/qwen3-5-small-models) — Artificial Analysis
- [Qwen 3.5 Small Models: The 9B Beats Last-Gen 30B](https://insiderllm.com/guides/qwen-3-5-small-models-9b-beats-30b/) — InsiderLLM
- [Qwen3.6-27B release](https://gigazine.net/gsc_news/en/20260423-qwen-3-6-27b/) — GIGAZINE
- [Google Launches Open Model Gemma 4](https://www.bernama.com/en/news.php?id=2540584) — Bernama
- [Can Gemma 4 26B A4B run on RTX 5080 16GB?](https://willitrunai.com/de/can-run/gemma-4-26b-a4b-on-rtx-5080-16gb) — WillItRunAI
- [EasySteer: A Unified Framework for LLM Steering](https://arxiv.org/pdf/2509.25175) — arXiv
- [vLLM Hook](https://github.com/IBM/vLLM-Hook) — IBM Research
