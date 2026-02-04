// AccelByte achievements debug panel - logic & Slate UI
// Encapsulates displaying a player's AccelByte achievements in a single .h/.cpp pair.

// AB_MCP_BEGIN:AccelByte.Achievements.Panel
// {
//   "service": "achievements",
//   "provider": "accelbyte",
//   "language": "unreal-cpp",
//   "description": "Demonstration of a self-contained Unreal Slate UI panel that queries AccelByte achievement definitions and user progress via the AccelByte Unreal SDK, merges them into a view-model, and renders a scrollable \"Achievements\" box with icons and progress.",
//   "controllerClass": "FAccelByteAchievementsPanel",
//   "entryStruct": "FAccelByteAchievementEntry",
//   "uiWidgetClass": "SAccelByteAchievementsWidget",
//   "rowWidgetClass": "SAccelByteAchievementRow",
//   "publicInterface": {
//     "initialise": "void Initialise(AccelByte::FApiClientPtr InApiClient, const FString& InLanguage = TEXT(\"en\"))",
//     "update": "void Update()",
//     "show": "void Show(float Width = 600.f, float Height = 500.f)",
//     "hide": "void Hide()",
//     "buildWidget": "TSharedRef<SWidget> BuildWidget(float Width = 600.f, float Height = 500.f)"
//   },
//   "asyncState": {
//     "definitionsLoadedFlag": "bDefinitionsLoaded",
//     "pendingUserUpdateFlag": "bPendingUserUpdate",
//     "pendingUserAchievementsField": "PendingUserAchievements"
//   },
//   "dataModel": {
//     "entriesField": "Entries",
//     "codeToIndexField": "CodeToIndex",
//     "fields": {
//       "AchievementCode": "FString",
//       "Name": "FText",
//       "Description": "FText",
//       "LockedIconUrl": "FString",
//       "UnlockedIconUrl": "FString",
//       "bUnlocked": "bool",
//       "CurrentValue": "float",
//       "TargetValue": "float"
//     }
//   },
//   "moduleDependencies": ["Slate", "SlateCore", "HTTP", "ImageWrapper"],
//   "integrationHints": ["Install the AccelByte Unreal SDK first (use the install_unreal_sdk tool) if not already installed. Then add these to PublicDependencyModuleNames in your module's .Build.cs: Slate, SlateCore, HTTP (for icon download), ImageWrapper (for decoding achievement icons), and your AccelByte SDK module."]
// }
// AB_MCP_END:AccelByte.Achievements.Panel

#pragma once

#include "CoreMinimal.h"
#include "SlateBasics.h"
#include "SlateExtras.h"

// HTTP for icon download
#include "Interfaces/IHttpRequest.h"
#include "HttpModule.h"

// AccelByte SDK
#include "Core/AccelByteApiClient.h"
#include "Core/AccelByteError.h"
#include "Models/AccelByteAchievementModels.h"

class SAccelByteAchievementsWidget;

/**
 * Lightweight view-model for a single achievement entry.
 * Holds definition data (name, description, goal, icons) and the current user's state.
 */
struct FAccelByteAchievementEntry
{
	FString AchievementCode;
	FText Name;
	FText Description;

	FString LockedIconUrl;
	FString UnlockedIconUrl;

	// Whether the achievement is currently unlocked for the player
	bool bUnlocked = false;

	// Progress values (for incremental achievements)
	float CurrentValue = 0.0f;
	float TargetValue = 0.0f;

	// Slate icon brush (created from downloaded texture, if any)
	TSharedPtr<FSlateBrush> IconBrush;
};

/**
 * Controller / logic class that:
 * - Loads and caches achievement definitions from AccelByte.
 * - Fetches the current player's achievement progress.
 * - Owns the Slate widget used to render the achievements.
 *
 * Public API:
 * - Initialise: load achievement definitions (descriptions, icons, goal values).
 * - Update:     fetch latest player achievement state.
 * - Show/Hide:  add or remove the Slate panel from the viewport.
 */
class FAccelByteAchievementsPanel : public TSharedFromThis<FAccelByteAchievementsPanel>
{
public:
	~FAccelByteAchievementsPanel();
	
	/**
	 * Initialize the panel by providing an AccelByte API client.
	 *
	 * @param InApiClient Valid AccelByte API client for the logged-in user.
	 * @param InLanguage  Optional language code (ISO 639-1), e.g. "en".
	 */
	void Initialise(AccelByte::FApiClientPtr InApiClient, const FString& InLanguage = TEXT("en"));

	/** Fetch latest player achievement state from AccelByte. */
	void Update();

	/**
	 * Show the achievements panel.
	 * Creates the Slate widget if needed and adds it to the game viewport.
	 */
	void Show(float Width = 600.f, float Height = 500.f);

	/** Hide the achievements panel and remove it from the viewport. */
	void Hide();

	/** Access the underlying Slate widget (for custom integration if desired). */
	TSharedPtr<SWidget> GetWidget() const;

	/**
	 * Build (or return) the Slate widget representing this panel.
	 * Does NOT add it to the viewport; callers control placement and lifetime.
	 */
	TSharedRef<SWidget> BuildWidget(float Width = 600.f, float Height = 500.f);

private:
	// Internal helpers for AccelByte async callbacks
	void OnQueryDefinitionsSuccess(const FAccelByteModelsPaginatedPublicAchievement& Result);
	void OnQueryUserAchievementsSuccess(const FAccelByteModelsPaginatedUserAchievement& Result);
	void OnAccelByteError(int32 ErrorCode, const FString& ErrorMessage);

	// Merge user achievement progress into the cached definitions
	void ApplyUserAchievements(const TArray<FAccelByteModelsUserAchievement>& UserAchievements);

	// Icon loading helper
	void DownloadIconForEntry(int32 Index, const FString& IconUrl);
	void OnIconDownloadComplete(FHttpRequestPtr Request, FHttpResponsePtr Response, bool bWasSuccessful, int32 ItemIndex);

	// UI helpers
	void EnsureWidgetCreated(float Width, float Height);
	void RefreshWidget();

private:
	AccelByte::FApiClientPtr ApiClient;
	FString Language;

	// Cached achievement entries (definitions + per-user state)
	TArray<TSharedPtr<FAccelByteAchievementEntry>> Entries;

	// Lookup from achievement code to index in Entries array
	TMap<FString, int32> CodeToIndex;

	// Slate widget instance
	TSharedPtr<SAccelByteAchievementsWidget> Widget;

	// Root widget added to the viewport when Show() is called
	TSharedPtr<SWidget> RootWidget;
	bool bVisible = false;

	// Async state flags to avoid race between definitions and user progress
	bool bDefinitionsLoaded = false;
	bool bPendingUserUpdate = false;

	// Cached user achievements if they arrive before definitions are loaded
	TArray<FAccelByteModelsUserAchievement> PendingUserAchievements;
};

/**
 * Slate row widget for a single achievement entry.
 */
class SAccelByteAchievementRow : public STableRow<TSharedPtr<FAccelByteAchievementEntry>>
{
public:
	SLATE_BEGIN_ARGS(SAccelByteAchievementRow) {}
		SLATE_ARGUMENT(TSharedPtr<FAccelByteAchievementEntry>, Item)
	SLATE_END_ARGS()

	void Construct(const FArguments& InArgs, const TSharedRef<STableViewBase>& OwnerTableView);

private:
	TSharedPtr<FAccelByteAchievementEntry> Item;
	TSharedPtr<SImage> IconImage;

	/** Bound brush getter so icons update automatically when the entry's brush changes. */
	const FSlateBrush* GetIconBrush() const;

	// Bound getters so progress text and bar update automatically when values change.
	TOptional<float> GetProgressPercent() const;
	FText GetProgressText() const;

	TSharedRef<SWidget> BuildContent();
};

/**
 * Slate widget that shows a titled panel "Achievements" with a scrollable list of entries.
 */
class SAccelByteAchievementsWidget : public SCompoundWidget
{
public:
	SLATE_BEGIN_ARGS(SAccelByteAchievementsWidget)
		: _Width(600.f)
		, _Height(500.f)
	{}
		SLATE_ARGUMENT(float, Width)
		SLATE_ARGUMENT(float, Height)
		SLATE_ARGUMENT(TArray<TSharedPtr<FAccelByteAchievementEntry>>*, ItemsSource)
	SLATE_END_ARGS()

	void Construct(const FArguments& InArgs);

	/** Request the list view to refresh after data changes. */
	void RequestRefresh();

private:
	TArray<TSharedPtr<FAccelByteAchievementEntry>>* Items = nullptr;
	TSharedPtr<SListView<TSharedPtr<FAccelByteAchievementEntry>>> ListView;

	TSharedRef<ITableRow> OnGenerateRow(TSharedPtr<FAccelByteAchievementEntry> Item, const TSharedRef<STableViewBase>& OwnerTable);
};

