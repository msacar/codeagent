Aider, sembol türlerini hiçbir şekilde takip etmiyor. 
Kod deposu haritalama (repo-map) adımında yalnızca isimlerle ve bir yakalamanın `def` (tanım) mi yoksa `ref` (referans) mi olduğuyla ilgileniyor.
Tree-sitter sorgu yakalamalarına bakıyor ve etiketi `name.definition.` (tanım) veya `name.reference.` (referans) ile başlayan her şeyi tutuyor.
Kaydettiği "tür" ise "class" | "method" | "constructor" gibi ayrımlara girmeden sadece "def" veya "ref" oluyor. 
İsimler doğrudan `node.text`'ten alınıyor.

Eğer bir dilin sorguları `ref` üretmezse, Aider bir "tokenizer" (ayrıştırıcı) adımıyla eksik `ref`'leri tamamlıyor.
Hiç `ref`'i olmayan `def`'ler gördükten sonra Pygments'ı çalıştırıyor, her `Token.Name`'i topluyor ve bunları `ref` olarak kabul ediyor.
Bu yaklaşım, dile özgü bir çıkarım yapmadan grafiği sıralama için yeterince yoğun tutuyor.

Sorgu dosyası seçimi tam da senin tarif ettiğin gibi işliyor. 
Dil paketiyle çalışırken `queries/tree-sitter-language-pack/{lang}-tags.scm` dosyasını tercih ediyor, 
eğer bu yoksa `queries/tree-sitter-languages/{lang}-tags.scm` dosyasına geri dönüyor.
Yani fark ettiğin "iki klasör" de destekleniyor; paket mevcut olduğunda ona öncelik veriliyor.

Sonraki tüm mantık, türe değil isme dayalı işliyor.
Aider, "hangi tanımlanmış belirteci kim referans alıyor" ilişkisine dayalı bir PageRank grafiği oluşturuyor ve bu bağlantıları (kenarları) ağırlıklandırıyor;
bu sıralama içinde yapıcı metot/metot/sınıf gibi bir mantık kesinlikle yer almıyor.
Daha sonra, bu isim düğümlerinin (name nodes) geçtiği satırları kullanarak `TreeContext` ile bağlamı oluşturuyor.
Tekrar belirtmek gerekirse: hiçbir sembol türü sınıflandırması yapılmıyor.
