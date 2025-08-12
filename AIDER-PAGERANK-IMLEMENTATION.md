Elbette, yazılım geliştirme terimlerini koruyarak istediğiniz metnin Türkçe çevirisi aşağıdadır:

Kısa cevap: Aider, tüm repodan tek tek fonksiyon gövdelerini tahmin etmez. LLM'e (Büyük Dil Modeli) şunları verir:

*   açıkça "sohbete eklediğiniz" dosyaların tam metnini (bunlar düzenlenir) ve
*   reponun geri kalanı için, bir `graph-ranking` geçişi aracılığıyla bir `token` bütçesine sığacak şekilde seçilmiş kompakt bir `repo` haritası (sadece dosya listeleri + anahtar `sembol` tanımları/`signature`'ları + birkaç "kritik satır"). Bu haritadan LLM, hangi diğer dosyalara ihtiyacı olduğuna karar verir ve Aider'dan bunları eklemesini ister; `/context` komutu da artık bu dosyaları otomatik olarak tanımlayabilir.

Aider'ın kullandığı akış şu şekildedir:

1.  **Bir `repo` haritası oluşturur** (bir kez, sonra gerektiğinde yenilenir). `Tree-sitter` sorguları `sembol` tanımlarını (`class`'lar/`function`'lar/`method`'lar) ve bunların adlarını/`signature`'larını çıkarır; harita, LLM'in tam gövdeler olmadan API'leri anlaması için her tanımın etrafındaki "kritik satırları" gösterir.
2.  **Haritayı `token`'lara sığdırmak için sıralar ve kırpar.** Bir `dependency graph` (düğümler = dosyalar; kenarlar = kullanır/bağlıdır) oluşturur ve mevcut `--map-tokens` bütçesi dahilinde sığacak en ilgili dilimleri seçmek için PageRank benzeri bir algoritma çalıştırır.
3.  **Her istekte `context` gönderir.** Aider her zaman (a) sohbet dosyalarınızın tam içeriğini artı (b) kırpılmış `repo` haritasını gönderir. Eğer LLM, `signature`'lardan/kritik satırlardan daha fazlasına ihtiyaç duyduğuna karar verirse (örneğin, başka bir dosyadaki bir `function` gövdesi), o dosyayı eklemeyi ister ve Aider onu dahil etmeyi teklif eder.
4.  **Hedeflerin otomatik seçimi (yeni).** `/context` komutu, bir istek için "hangi dosyaların düzenlenmesi gerektiğini otomatik olarak tanımlayabilir", aslında eklenecek dosyaları önermek için aynı harita/grafik sinyallerini kullanır.

Bunun `feature`/`bug-fix`/`refactor` için anlamı şudur:

*   **Feature**: Muhtemel hedef dosya(ları) eklersiniz. Aider bu gövdeleri + ilgili `module`/`interface`'lerin sıralanmış bir haritasını gönderir. LLM, `signature`'ları gördükten sonra bitişik dosyaları (örneğin, `route`'lar, `type`'lar) eklemeyi isteyebilir.
*   **Bug fix**: Dosya eklemezseniz, Aider yine de bir harita gönderir; LLM, hatalı `function`'ı tanımlayan `module`'ü tam olarak belirlemek için bunu kullanabilir ve o dosyanın gövdesini isteyebilir. Veya Aider'ın `edit set`'ini önermesine izin vermek için `/context` komutunu çalıştırın.
*   **Refactor**: Aynı düzen—sohbet dosyaları gövdeleri içerir; harita, LLM'in etkilenen tüm `sembol`'leri bulabilmesi ve ardından gerekirse daha fazla dosya eklemeyi isteyebilmesi için `cross-reference`'lar sağlar.

İsterseniz, bu davranışı sizin `pipeline`'ınızda yansıtabilirim: yalnızca "`edit set`" dosyaları için tam metin gönderin ve diğer her şey için sıralanmış, `token` ile sınırlandırılmış bir harita (`defs` + kısa `context`) gönderin. Bu, dile özgü kuralları sürdürmeden Aider'ın stratejisiyle yakından eşleşecektir.
