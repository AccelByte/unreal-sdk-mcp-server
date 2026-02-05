// AccelByte login/register panel - logic & Slate UI
// Drop-in panel for username/password login, register (device ID then upgrade headless), and logout via AccelByte OSS.

// AB_MCP_BEGIN:AccelByte.Login.Panel
// {
//   "service": "auth",
//   "provider": "accelbyte",
//   "language": "unreal-cpp",
//   "description": "Self-contained Unreal Slate UI panel for AccelByte authentication: username/password login, account registration (device ID then headless upgrade), and logout. Covers auth, user identity, account creation, login, logout, credentials (username, password), sign-in, sign-out.",
//   "keywords": ["login", "auth", "authentication", "account", "username", "password", "user", "identity", "credentials", "register", "logout", "sign-in", "sign-out", "headless", "upgrade"],
//   "controllerClass": "FAccelByteLoginPanel",
//   "uiWidgetClass": "SAccelByteLoginWidget",
//   "stateEnum": "ELoginPanelState",
//   "publicInterface": {
//     "initialise": "void Initialise()",
//     "show": "void Show(float Width = 400.f, float Height = 380.f)",
//     "hide": "void Hide()",
//     "buildWidget": "TSharedRef<SWidget> BuildWidget(float Width = 400.f, float Height = 380.f)",
//     "onLoginClicked": "void OnLoginClicked(const FString& Username, const FString& Password)",
//     "onRegisterClicked": "void OnRegisterClicked(const FString& Username, const FString& Password, const FString& DisplayName)",
//     "onLogoutClicked": "void OnLogoutClicked()"
//   },
//   "asyncState": {
//     "stateField": "State",
//     "registerPendingFlag": "bRegisterPending",
//     "pendingRegisterUsernameField": "PendingRegisterUsername",
//     "pendingRegisterPasswordField": "PendingRegisterPassword"
//   },
//   "moduleDependencies": ["Slate", "SlateCore", "OnlineSubsystem"],
//   "integrationHints": ["Install the AccelByte Unreal SDK first (use the install_unreal_sdk tool) if not already installed. Then add these to PublicDependencyModuleNames in your module's .Build.cs: Slate, SlateCore, OnlineSubsystem (for identity/login), and your AccelByte SDK module."]
// }
// AB_MCP_END:AccelByte.Login.Panel

#pragma once

#include "CoreMinimal.h"
#include "SlateBasics.h"
#include "SlateExtras.h"
#include "Interfaces/OnlineIdentityInterface.h"
#include "Models/AccelByteUserModels.h"

class SAccelByteLoginWidget;
class FOnlineSubsystemAccelByte;
class FOnlineIdentityAccelByte;

/** Auth state for the login panel. */
enum class ELoginPanelState
{
	LoggedOut,
	LoggingIn,
	LoggedIn,
	LoggingOut
};

/**
 * Controller class that handles login, register (device ID then upgrade headless), and logout via AccelByte OSS.
 * Does not take an ApiClient; uses OSS Identity and, for register, gets ApiClient after device login to call Upgrade.
 */
class FAccelByteLoginPanel : public TSharedFromThis<FAccelByteLoginPanel>
{
public:
	~FAccelByteLoginPanel();
	
	void Initialise();
	void Show(float Width = 400.f, float Height = 430.f);
	void Hide();
	bool IsVisible() const { return bVisible; }
	TSharedPtr<SWidget> GetWidget() const;
	TSharedRef<SWidget> BuildWidget(float Width = 400.f, float Height = 430.f);

	ELoginPanelState GetState() const { return State; }
	bool IsLoggedIn() const { return State == ELoginPanelState::LoggedIn; }
	FString GetErrorText() const { return ErrorText; }
	bool IsRegisterMode() const { return bRegisterMode; }
	void SetRegisterMode(bool bInRegisterMode) { bRegisterMode = bInRegisterMode; ErrorText.Empty(); RefreshWidget(); }

	FString GetStoredUsername() const { return StoredUsername; }
	FString GetStoredPassword() const { return StoredPassword; }
	FString GetStoredDisplayName() const { return StoredDisplayName; }
	void SetStoredUsername(const FString& S) { StoredUsername = S; }
	void SetStoredPassword(const FString& S) { StoredPassword = S; }
	void SetStoredDisplayName(const FString& S) { StoredDisplayName = S; }
	void ClearStoredCredentials() { StoredUsername.Empty(); StoredPassword.Empty(); StoredDisplayName.Empty(); }

	void OnLoginClicked(const FString& Username, const FString& Password);
	void OnRegisterClicked(const FString& Username, const FString& Password, const FString& DisplayName);
	void OnDeviceIdLoginClicked();
	void OnLogoutClicked();
	void OnBackToLoginClicked();

private:
	void OnLoginComplete(int32 LocalUserNum, bool bWasSuccessful, const FUniqueNetId& UserId, const FString& Error);
	void OnLogoutComplete(int32 LocalUserNum, bool bWasSuccessful, const class FOnlineErrorAccelByte& Error);
	void OnUpgradeSuccess(const struct FAccountUserData& Response);
	void OnUpgradeError(int32 ErrorCode, const FString& ErrorMessage);
	void UnbindLoginDelegate();
	void UnbindLogoutDelegate();
	void EnsureWidgetCreated(float Width, float Height);
	void RefreshWidget();
	void SetState(ELoginPanelState NewState);
	void SetError(const FString& InError);

private:
	ELoginPanelState State = ELoginPanelState::LoggedOut;
	FString ErrorText;
	bool bRegisterMode = false;
	bool bVisible = false;
	bool bRegisterPending = false;
	FString PendingRegisterUsername;
	FString PendingRegisterPassword;
	FString StoredUsername;
	FString StoredPassword;
	FString StoredDisplayName;
	FDelegateHandle LoginCompleteHandle;
	FDelegateHandle LogoutCompleteHandle;
	TSharedPtr<SAccelByteLoginWidget> Widget;
	TSharedPtr<SWidget> RootWidget;
};

/**
 * Slate widget for login/register form, throbber, and Logout button.
 */
class SAccelByteLoginWidget : public SCompoundWidget
{
public:
	SLATE_BEGIN_ARGS(SAccelByteLoginWidget)
		: _Width(400.f)
		, _Height(430.f)
	{}
		SLATE_ARGUMENT(float, Width)
		SLATE_ARGUMENT(float, Height)
		SLATE_ARGUMENT(FAccelByteLoginPanel*, Panel)
	SLATE_END_ARGS()

	void Construct(const FArguments& InArgs);
	void RequestRefresh();
	/** Set keyboard focus to the first text box (username) when the form is visible. */
	void RequestFocusOnFirstEdit();

	// Allow this widget to receive keyboard focus so the panel steals input from the editor
	virtual bool SupportsKeyboardFocus() const override { return true; }
	// Consume all key events so they don't propagate to the viewport/editor (e.g. @ shortcut)
	virtual FReply OnKeyDown(const FGeometry& MyGeometry, const FKeyEvent& InKeyEvent) override;
	virtual FReply OnKeyChar(const FGeometry& MyGeometry, const FCharacterEvent& InCharacterEvent) override;

private:
	TSharedRef<SWidget> BuildContent();
	TSharedRef<SWidget> BuildLoginForm();
	TSharedRef<SWidget> BuildRegisterForm();
	TSharedRef<SWidget> BuildThrobberOverlay();
	TSharedRef<SWidget> BuildLoggedInContent();

	FAccelByteLoginPanel* Panel = nullptr;
	float Width = 400.f;
	float Height = 380.f;
	TSharedPtr<SEditableTextBox> UsernameEdit;
	TSharedPtr<SEditableTextBox> PasswordEdit;
	TSharedPtr<SEditableTextBox> DisplayNameEdit;
	TSharedPtr<SBox> ContentContainer;
};
