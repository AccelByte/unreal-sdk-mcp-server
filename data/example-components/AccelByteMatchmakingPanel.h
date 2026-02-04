// AccelByte matchmaking panel - logic & Slate UI
// Drop-in panel for P2P matchmaking via AccelByte OSS.

// AB_MCP_BEGIN:AccelByte.Matchmaking.Panel
// {
//   "service": "matchmaking",
//   "provider": "accelbyte",
//   "language": "unreal-cpp",
//   "description": "Self-contained Unreal Slate UI panel for AccelByte P2P matchmaking: Quick Play with automatic party session creation, session restoration, match finding, and session joining. Covers matchmaking, sessions, multiplayer, online play, party system, lobby management.",
//   "keywords": ["matchmaking", "sessions", "multiplayer", "P2P", "peer-to-peer", "quick play", "party", "lobby", "join", "search", "find match", "online play", "game session", "party session", "cancel matchmaking"],
//   "controllerClass": "FAccelByteMatchmakingPanel",
//   "uiWidgetClass": "SAccelByteMatchmakingWidget",
//   "stateEnum": "EMatchmakingPanelState",
//   "publicInterface": {
//     "initialise": "void Initialise()",
//     "show": "void Show(float Width = 400.f, float Height = 300.f)",
//     "hide": "void Hide()",
//     "buildWidget": "TSharedRef<SWidget> BuildWidget(float Width = 400.f, float Height = 300.f)",
//     "onQuickPlayClicked": "void OnQuickPlayClicked()",
//     "onCancelClicked": "void OnCancelClicked()"
//   },
//   "asyncState": {
//     "stateField": "State",
//     "matchmakingSessionNameField": "MatchmakingSessionName",
//     "partySessionNameField": "PartySessionName",
//     "searchHandleField": "SearchHandle"
//   },
//   "moduleDependencies": ["Slate", "SlateCore", "OnlineSubsystem"],
//   "engineConfiguration": {
//     "DefaultEngine.ini": {
//       "OnlineSubsystemAccelByte": {
//         "bAutoLobbyConnectAfterLoginSuccess": "true",
//         "bEnableV2Sessions": "true"
//       },
//       "AccelByteNetworkUtilities": {
//         "bNonSeamlessTravelUseNewConnection": "true",
//         "HostCheckTimeout": "5",
//         "UseTurnManager": "true"
//       }
//     }
//   },
//   "integrationHints": ["Install the AccelByte Unreal SDK first (use the install_unreal_sdk tool) if not already installed. Then add these to PublicDependencyModuleNames in your module's .Build.cs: Slate, SlateCore, OnlineSubsystem (for session/matchmaking), and your AccelByte SDK module. Required DefaultEngine.ini settings: [OnlineSubsystemAccelByte] bAutoLobbyConnectAfterLoginSuccess=true, bEnableV2Sessions=true; [AccelByteNetworkUtilities] bNonSeamlessTravelUseNewConnection=true, HostCheckTimeout=5, UseTurnManager=true."]
// }
// AB_MCP_END:AccelByte.Matchmaking.Panel

#pragma once

#include "CoreMinimal.h"
#include "SlateBasics.h"
#include "SlateExtras.h"
#include "Interfaces/OnlineSessionInterface.h"
#include "OnlineSessionSettings.h"

class SAccelByteMatchmakingWidget;
class FOnlineSessionSearchAccelByte;

/** Matchmaking state for the panel. */
enum class EMatchmakingPanelState
{
	Idle,
	RestoringParties,
	CreatingParty,
	Searching,
	MatchFound,
	Joining,
	InSession,
	Cancelling,
	Error
};

/**
 * Controller class that handles P2P matchmaking via AccelByte OSS.
 * Provides Quick Play functionality with automatic session joining.
 */
class FAccelByteMatchmakingPanel : public TSharedFromThis<FAccelByteMatchmakingPanel>
{
public:
	void Initialise();
	void Show(float Width = 400.f, float Height = 300.f);
	void Hide();
	TSharedPtr<SWidget> GetWidget() const;
	TSharedRef<SWidget> BuildWidget(float Width = 400.f, float Height = 300.f);

	EMatchmakingPanelState GetState() const { return State; }
	FString GetStatusText() const { return StatusText; }
	FString GetErrorText() const { return ErrorText; }
	bool IsSearching() const { return State == EMatchmakingPanelState::Searching || State == EMatchmakingPanelState::Cancelling; }
	bool CanStartMatchmaking() const { return State == EMatchmakingPanelState::Idle || State == EMatchmakingPanelState::Error; }
	bool CanCancel() const { return State == EMatchmakingPanelState::Searching; }

	void OnQuickPlayClicked();
	void OnCancelClicked();

private:
	/** Check if already in a party session */
	bool IsInPartySession() const;

	/** Restore any existing party sessions from the backend */
	void RestorePartySessions();

	/** Called when party session restoration completes */
	void OnRestoreActiveSessionsComplete(const FUniqueNetId& LocalUserId, const struct FOnlineError& Result);

	/** Create a party session before matchmaking */
	void CreatePartySession();

	/** Called when party session creation completes */
	void OnCreateSessionComplete(FName SessionName, bool bWasSuccessful);

	/** Start actual matchmaking (called after party is created) */
	void StartMatchmakingInternal();

	void OnStartMatchmakingComplete(FName SessionName, const struct FOnlineError& ErrorDetails, const struct FSessionMatchmakingResults& Results);
	void OnJoinSessionComplete(FName SessionName, EOnJoinSessionCompleteResult::Type Result);
	void OnCancelMatchmakingComplete(FName SessionName, bool bWasSuccessful);

	void SetState(EMatchmakingPanelState NewState);
	void SetStatus(const FString& InStatus);
	void SetError(const FString& InError);
	void EnsureWidgetCreated(float Width, float Height);
	void RefreshWidget();
	void UnbindDelegates();

private:
	EMatchmakingPanelState State = EMatchmakingPanelState::Idle;
	FString StatusText;
	FString ErrorText;
	bool bVisible = false;

	/** Session name used for matchmaking */
	FName MatchmakingSessionName = NAME_None;

	/** Party session name */
	FName PartySessionName = NAME_None;

	/** Search handle for current matchmaking request */
	TSharedPtr<FOnlineSessionSearchAccelByte> SearchHandle;

	/** Delegate handles */
	FDelegateHandle JoinSessionCompleteHandle;
	FDelegateHandle CreateSessionCompleteHandle;
	FDelegateHandle CancelMatchmakingCompleteHandle;

	TSharedPtr<SAccelByteMatchmakingWidget> Widget;
	TSharedPtr<SWidget> RootWidget;
};

/**
 * Slate widget for matchmaking panel with Quick Play, Cancel, and status display.
 */
class SAccelByteMatchmakingWidget : public SCompoundWidget
{
public:
	SLATE_BEGIN_ARGS(SAccelByteMatchmakingWidget)
		: _Width(400.f)
		, _Height(300.f)
	{}
		SLATE_ARGUMENT(float, Width)
		SLATE_ARGUMENT(float, Height)
		SLATE_ARGUMENT(FAccelByteMatchmakingPanel*, Panel)
	SLATE_END_ARGS()

	void Construct(const FArguments& InArgs);
	void RequestRefresh();

	virtual bool SupportsKeyboardFocus() const override { return true; }

private:
	TSharedRef<SWidget> BuildContent();

	FAccelByteMatchmakingPanel* Panel = nullptr;
	float Width = 400.f;
	float Height = 300.f;
	TSharedPtr<SBox> ContentContainer;
};
