# Codex ve Claude Code için AugeLab

Görüntü işleme ve görsel kontrolden model eğitimine, AugeLab Studio ile bilgisayarlı
görü ve yapay zekâ iş akışları oluşturun. Tek bir `augelab` becerisi, çalışan
AugeLab Studio'nun mevcut MCP araçlarına bağlanır.
Studio'nun blok kataloğu ve iş akışları plugin içinde kopyalanmaz.

**0.1.5 beta:** İlk kurulum akışı, Windows veya Linux'ta Studio eksikse platforma
uygun resmi S3 yükleyicisini indirir, SHA-256 değerini doğrular ve kurar; hesap
kaydı, e-posta doğrulaması ve lisans aktivasyonuna yardımcı olur.

Desteklenen hedefler **Windows x64** ve **Linux x86-64/ARM64**. **macOS desteklenmez.**

## İlk kurulum

Studio ve ajan aynı bilgisayarda çalışmalı. Windows x64'te ajan, Studio kurulu
değilse AWS'deki resmi EXE'yi indirir, SHA-256 değerini doğrular, kullanıcı
klasörüne sessiz kurulum yapar ve Studio'yu açar. Kurulu Studio varsa onu kullanır.
Linux'ta Python 3.9+, bash ve yerel grafik masaüstü oturumu gerekir. Yardımcı,
mimariye uygun resmi yükleyiciyi `--ui` ile çalıştırır; `~/studio_venv`,
`~/.local/bin/augelab_studio` ve masaüstü kısayollarını oluşturur. Masaüstü
kullanıcısı olarak çalıştırın; yükleyici sistem bağımlılıkları için sudo isteyebilir.
Yalnızca headless kurulum, bu masaüstü MCP bağlantısının yerine geçmez.
İsteğe bağlı GPU/AI paketi, uygun donanımda ihtiyaç olduğunda ayrıca eklenir.

Lisans gerekiyorsa ajan [resmi hesap sayfasından](https://account.augelab.com)
kayıt/giriş akışını yürütür. İzin verilmiş Gmail veya Outlook bağlantısından
ilgili doğrulama e-postasını okuyup hesabı doğrular; kullanıcının kendi lisans
anahtarını Studio'ya girer. Gerekli giriş, parola, sözleşme, CAPTCHA veya MFA
adımlarını kullanıcı tamamlar. Araçlar veya lisans yoksa ajan kalan adımları anlatır.
Plugin lisans sağlamaz; anahtarların sohbete yapıştırılması gerekmez.

Aktivasyondan sonra Studio'da **Chat > Settings > MCP > Start** ile sunucu
başlatılır. Varsayılan adres `http://127.0.0.1:8765/mcp`.

## Codex kurulumu

`AugelabTech/augelab-codex-claude-plugin` deposundan kurulum:

```sh
codex plugin marketplace add AugelabTech/augelab-codex-claude-plugin
codex plugin add augelab@augelab-plugins
```

Kurulumdan sonra sunulursa **Run setup / Kurulumu tamamla** seçeneğini çalıştırın.
İndirme bu kurulum sohbetinde başlar. Eski istemcilerde yeni bir yerel sohbet açın:

> $augelab Studio'yu bu bilgisayara kur, bağlı Gmail veya Outlook hesabımla kayıt ve lisans aktivasyonunu tamamlamama yardım et.

## Claude Code kurulumu

Claude Code içinde:

```text
/plugin marketplace add AugelabTech/augelab-codex-claude-plugin
/plugin install augelab@augelab-plugins
```

Yeni oturumda `/augelab:augelab Studio'yu kur ve lisans aktivasyonunu tamamla` kullanın.
Bu paket Claude Code içindir;
Claude Desktop'ın ayrı sohbet bağlantı ayarları için değildir.

## Yerel ZIP kurulumu

`augelab-marketplace-0.1.5.zip` arşivini çıkarın. Codex için çıkarılan klasörde
`codex plugin marketplace add .`, ardından `codex plugin add augelab@augelab-plugins`
çalıştırın. Claude Code için `claude plugin marketplace add .`, ardından
`claude plugin install augelab@augelab-plugins` kullanın.

Studio farklı port gösteriyorsa yerel kopyadaki `plugins/augelab/.mcp.json` adresini
güncelleyin ve plugini yeniden kurun. Kayıtlı port yerine **aktif portu** esas alın.
Aynı isimli yerel ve Git marketplace kaynaklarını birlikte eklemeyin.

[Ayrıntılı rehber](README.md) · [Canlı test adımları](docs/smoke-test.md)
