# Homebrew formula template.
# Put this in a repo named  homebrew-tap  (as Formula/aura.rb), then people run:
#   brew install umer-farooq230/tap/aura
# After each release, update `version` and the four sha256 values:
#   shasum -a 256 aura-macos-arm64   (etc.)
class Aura < Formula
  desc "ASCII portraits in your terminal"
  homepage "https://github.com/umer-farooq230/aura"
  version "0.1.0"

  on_macos do
    on_arm do
      url "https://github.com/umer-farooq230/aura/releases/download/v#{version}/aura-macos-arm64"
      sha256 "REPLACE_ME"
    end
    on_intel do
      url "https://github.com/umer-farooq230/aura/releases/download/v#{version}/aura-macos-x64"
      sha256 "REPLACE_ME"
    end
  end

  on_linux do
    on_intel do
      url "https://github.com/umer-farooq230/aura/releases/download/v#{version}/aura-linux-x64"
      sha256 "REPLACE_ME"
    end
  end

  def install
    binary = Dir["aura-*"].first
    bin.install binary => "aura"
  end

  test do
    assert_match "aura", shell_output("#{bin}/aura --version")
  end
end
