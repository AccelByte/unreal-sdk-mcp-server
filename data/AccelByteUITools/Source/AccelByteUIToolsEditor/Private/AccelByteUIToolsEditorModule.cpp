// Copyright (c) 2026 AccelByte Inc. All Rights Reserved.

#include "AccelByteUIToolsEditorModule.h"

#include "EditorAssetLibrary.h"
#include "HttpPath.h"
#include "HttpRequestHandler.h"
#include "HttpServerModule.h"
#include "HttpServerRequest.h"
#include "HttpServerResponse.h"
#include "IHttpRouter.h"
#include "ILiveCodingModule.h"
#include "Misc/Crc.h"
#include "Modules/ModuleManager.h"
#include "Policies/CondensedJsonPrintPolicy.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "AccelByteUIToolsLibrary.h"
#include "BlueprintCompilationManager.h"
#include "Blueprint/UserWidget.h"
#include "WidgetBlueprint.h"

#define LOCTEXT_NAMESPACE "FAccelByteUIToolsEditorModule"

namespace
{
constexpr uint32 WidgetGeneratorBridgePort = 48757;

DEFINE_LOG_CATEGORY_STATIC(LogAccelByteUIToolsBridge, Log, All);

FString ToJsonText(const TSharedRef<FJsonObject>& JsonObject)
{
	FString JsonText;
	const TSharedRef<TJsonWriter<TCHAR, TCondensedJsonPrintPolicy<TCHAR>>> Writer =
		TJsonWriterFactory<TCHAR, TCondensedJsonPrintPolicy<TCHAR>>::Create(&JsonText);
	FJsonSerializer::Serialize(JsonObject, Writer);
	return JsonText;
}

TUniquePtr<FHttpServerResponse> JsonResponse(const TSharedRef<FJsonObject>& Body, const EHttpServerResponseCodes Code = EHttpServerResponseCodes::Ok)
{
	TUniquePtr<FHttpServerResponse> Response = FHttpServerResponse::Create(ToJsonText(Body), TEXT("application/json"));
	Response->Code = Code;
	return Response;
}

void CompleteJson(const FHttpResultCallback& OnComplete, const TSharedRef<FJsonObject>& Body, const EHttpServerResponseCodes Code = EHttpServerResponseCodes::Ok)
{
	TUniquePtr<FHttpServerResponse> Response = JsonResponse(Body, Code);
	OnComplete(MoveTemp(Response));
}

void AddError(const TSharedRef<FJsonObject>& Report, const FString& Code, const FString& Message)
{
	TArray<TSharedPtr<FJsonValue>> Errors = Report->GetArrayField(TEXT("errors"));
	const TSharedRef<FJsonObject> ErrorObject = MakeShared<FJsonObject>();
	ErrorObject->SetStringField(TEXT("code"), Code);
	ErrorObject->SetStringField(TEXT("message"), Message);
	Errors.Add(MakeShared<FJsonValueObject>(ErrorObject));
	Report->SetArrayField(TEXT("errors"), Errors);
}

bool HasErrors(const TSharedRef<FJsonObject>& Report)
{
	return !Report->GetArrayField(TEXT("errors")).IsEmpty();
}

void AddCollectionEntryAssignments(const TSharedRef<FJsonObject>& Report, const TArray<FString>& CollectionEntryAssignments)
{
	TArray<TSharedPtr<FJsonValue>> AssignmentValues;
	for (const FString& Assignment : CollectionEntryAssignments)
	{
		TArray<FString> Parts;
		Assignment.ParseIntoArray(Parts, TEXT("|"), false);

		const TSharedRef<FJsonObject> AssignmentObject = MakeShared<FJsonObject>();
		AssignmentObject->SetStringField(TEXT("widget_name"), Parts.IsValidIndex(0) ? Parts[0] : TEXT(""));
		AssignmentObject->SetStringField(TEXT("expected_entry_widget_class"), Parts.IsValidIndex(1) ? Parts[1] : TEXT(""));
		AssignmentObject->SetStringField(TEXT("actual_entry_widget_class"), Parts.IsValidIndex(2) ? Parts[2] : TEXT(""));
		AssignmentObject->SetBoolField(TEXT("verified"), Parts.IsValidIndex(3) && Parts[3].Equals(TEXT("true"), ESearchCase::IgnoreCase));
		AssignmentValues.Add(MakeShared<FJsonValueObject>(AssignmentObject));
	}
	Report->SetArrayField(TEXT("verified_collection_entries"), AssignmentValues);
}

void CollectExpectedCollectionEntries(const TSharedPtr<FJsonObject>& Node, TArray<TSharedPtr<FJsonValue>>& OutEntries)
{
	if (!Node.IsValid())
	{
		return;
	}

	FString WidgetType;
	FString WidgetName;
	FString EntryWidgetClass;
	if (Node->TryGetStringField(TEXT("type"), WidgetType)
		&& (WidgetType == TEXT("ListView") || WidgetType == TEXT("TileView") || WidgetType == TEXT("TreeView"))
		&& Node->TryGetStringField(TEXT("name"), WidgetName)
		&& Node->TryGetStringField(TEXT("entry_widget_class"), EntryWidgetClass)
		&& !WidgetName.IsEmpty()
		&& !EntryWidgetClass.IsEmpty())
	{
		const TSharedRef<FJsonObject> EntryObject = MakeShared<FJsonObject>();
		EntryObject->SetStringField(TEXT("widget_name"), WidgetName);
		EntryObject->SetStringField(TEXT("expected_entry_widget_class"), EntryWidgetClass);
		OutEntries.Add(MakeShared<FJsonValueObject>(EntryObject));
	}

	const TArray<TSharedPtr<FJsonValue>>* Children = nullptr;
	if (Node->TryGetArrayField(TEXT("children"), Children))
	{
		for (const TSharedPtr<FJsonValue>& ChildValue : *Children)
		{
			CollectExpectedCollectionEntries(ChildValue.IsValid() ? ChildValue->AsObject() : nullptr, OutEntries);
		}
	}
}

void AddExpectedCollectionEntries(const TSharedRef<FJsonObject>& Report, const TSharedPtr<FJsonObject>& Spec)
{
	TArray<TSharedPtr<FJsonValue>> EntryValues;
	if (Spec.IsValid())
	{
		const TSharedPtr<FJsonObject>* Root = nullptr;
		if (Spec->TryGetObjectField(TEXT("root"), Root) && Root != nullptr && Root->IsValid())
		{
			CollectExpectedCollectionEntries(*Root, EntryValues);
		}
	}
	Report->SetArrayField(TEXT("expected_collection_entries"), EntryValues);
}

void AddWidgetClassAssignments(const TSharedRef<FJsonObject>& Report, const TArray<FString>& WidgetClassAssignments)
{
	TArray<TSharedPtr<FJsonValue>> AssignmentValues;
	for (const FString& Assignment : WidgetClassAssignments)
	{
		TArray<FString> Parts;
		Assignment.ParseIntoArray(Parts, TEXT("|"), false);

		const TSharedRef<FJsonObject> AssignmentObject = MakeShared<FJsonObject>();
		AssignmentObject->SetStringField(TEXT("widget_name"), Parts.IsValidIndex(0) ? Parts[0] : TEXT(""));
		AssignmentObject->SetStringField(TEXT("expected_widget_class"), Parts.IsValidIndex(1) ? Parts[1] : TEXT(""));
		AssignmentObject->SetStringField(TEXT("actual_widget_class"), Parts.IsValidIndex(2) ? Parts[2] : TEXT(""));
		AssignmentObject->SetStringField(TEXT("class_stability"), Parts.IsValidIndex(3) ? Parts[3] : TEXT(""));
		AssignmentObject->SetBoolField(TEXT("verified"), Parts.IsValidIndex(4) && Parts[4].Equals(TEXT("true"), ESearchCase::IgnoreCase));
		AssignmentValues.Add(MakeShared<FJsonValueObject>(AssignmentObject));
	}
	Report->SetArrayField(TEXT("verified_widget_classes"), AssignmentValues);
}

void AddBackingBindingAssignments(const TSharedRef<FJsonObject>& Report, const TArray<FString>& BindingAssignments)
{
	TArray<TSharedPtr<FJsonValue>> AssignmentValues;
	for (const FString& Assignment : BindingAssignments)
	{
		TArray<FString> Parts;
		Assignment.ParseIntoArray(Parts, TEXT("|"), false);

		const TSharedRef<FJsonObject> AssignmentObject = MakeShared<FJsonObject>();
		AssignmentObject->SetStringField(TEXT("widget_name"), Parts.IsValidIndex(0) ? Parts[0] : TEXT(""));
		AssignmentObject->SetStringField(TEXT("expected_property_class"), Parts.IsValidIndex(1) ? Parts[1] : TEXT(""));
		AssignmentObject->SetStringField(TEXT("actual_property_class"), Parts.IsValidIndex(2) ? Parts[2] : TEXT(""));
		AssignmentObject->SetStringField(TEXT("binding_meta"), Parts.IsValidIndex(3) ? Parts[3] : TEXT(""));
		AssignmentObject->SetStringField(TEXT("parent_class"), Parts.IsValidIndex(4) ? Parts[4] : TEXT(""));
		AssignmentObject->SetBoolField(TEXT("verified"), Parts.IsValidIndex(5) && Parts[5].Equals(TEXT("true"), ESearchCase::IgnoreCase));
		AssignmentValues.Add(MakeShared<FJsonValueObject>(AssignmentObject));
	}
	Report->SetArrayField(TEXT("verified_backing_bindings"), AssignmentValues);
}

bool ParseRequestBody(const FHttpServerRequest& Request, TSharedPtr<FJsonObject>& OutBody, FString& OutError)
{
	if (Request.Body.IsEmpty())
	{
		OutError = TEXT("Request body must be a JSON object.");
		return false;
	}

	const FUTF8ToTCHAR BodyConverter(reinterpret_cast<const ANSICHAR*>(Request.Body.GetData()), Request.Body.Num());
	const FString BodyString(BodyConverter.Length(), BodyConverter.Get());
	const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(BodyString);
	if (!FJsonSerializer::Deserialize(Reader, OutBody) || !OutBody.IsValid())
	{
		OutError = TEXT("Request body must be a JSON object.");
		return false;
	}

	return true;
}

TSharedRef<FJsonObject> BuildBaseReport()
{
	const TSharedRef<FJsonObject> Report = MakeShared<FJsonObject>();
	Report->SetBoolField(TEXT("ok"), false);
	Report->SetArrayField(TEXT("errors"), TArray<TSharedPtr<FJsonValue>>());
	return Report;
}

bool RequireStringField(const TSharedRef<FJsonObject>& JsonObject, const TCHAR* FieldName, FString& OutValue, const TSharedRef<FJsonObject>& Report)
{
	if (!JsonObject->TryGetStringField(FieldName, OutValue) || OutValue.IsEmpty())
	{
		AddError(Report, TEXT("invalid_request"), FString::Printf(TEXT("Missing required string field: %s"), FieldName));
		return false;
	}

	return true;
}

bool RequireObjectField(const TSharedRef<FJsonObject>& JsonObject, const TCHAR* FieldName, TSharedPtr<FJsonObject>& OutValue, const TSharedRef<FJsonObject>& Report)
{
	const TSharedPtr<FJsonObject>* ObjectValue = nullptr;
	if (!JsonObject->TryGetObjectField(FStringView(FieldName), ObjectValue) || ObjectValue == nullptr || !ObjectValue->IsValid())
	{
		AddError(Report, TEXT("invalid_request"), FString::Printf(TEXT("Missing required object field: %s"), FieldName));
		return false;
	}

	OutValue = *ObjectValue;
	return true;
}

void AddParentClassLoadError(const TSharedRef<FJsonObject>& Report, const FString& ParentClassPath, const FString& Message)
{
	TArray<TSharedPtr<FJsonValue>> Errors = Report->GetArrayField(TEXT("errors"));
	const TSharedRef<FJsonObject> ErrorObject = MakeShared<FJsonObject>();
	ErrorObject->SetStringField(TEXT("code"), TEXT("parent_class_unavailable"));
	ErrorObject->SetStringField(TEXT("message"), Message);
	ErrorObject->SetStringField(TEXT("parent_class"), ParentClassPath);
	ErrorObject->SetStringField(
		TEXT("likely_cause"),
		TEXT("The requested final parent class is not loaded in this editor session. For newly generated C++ backing classes, Live Coding cannot register the new UCLASS; the editor needs a full rebuild/restart cycle that loads the class."));
	ErrorObject->SetStringField(
		TEXT("next_action"),
		TEXT("Keep the spec parent_class set to the final script-backed class. Do not swap to AGSCommonActivatableBase, CommonActivatableWidget, UUserWidget, AccelByteWarsWidgetEntry, or another fallback parent. For a new UCLASS, run a full Build.bat rebuild, reopen or reload the editor so the class is available, rerun style discovery/approval or accelbyte_ui_verify_backing_class, then call accelbyte_ui_generate with mode \"bridge\"."));
	Errors.Add(MakeShared<FJsonValueObject>(ErrorObject));
	Report->SetArrayField(TEXT("errors"), Errors);
}

TArray<TSharedPtr<FJsonValue>> MakeNumberArray(const double A, const double B, const double C, const double D)
{
	TArray<TSharedPtr<FJsonValue>> Values;
	Values.Add(MakeShared<FJsonValueNumber>(A));
	Values.Add(MakeShared<FJsonValueNumber>(B));
	Values.Add(MakeShared<FJsonValueNumber>(C));
	Values.Add(MakeShared<FJsonValueNumber>(D));
	return Values;
}

void SetArrayField(const TSharedRef<FJsonObject>& JsonObject, const TCHAR* FieldName, const double A, const double B, const double C, const double D)
{
	JsonObject->SetArrayField(FieldName, MakeNumberArray(A, B, C, D));
}

bool IsColorArray(const TArray<TSharedPtr<FJsonValue>>& Values, const double A, const double B, const double C, const double D)
{
	const double Expected[] = { A, B, C, D };
	if (Values.Num() < 4)
	{
		return false;
	}
	for (int32 Index = 0; Index < 4; ++Index)
	{
		if (!Values[Index].IsValid() || FMath::Abs(Values[Index]->AsNumber() - Expected[Index]) > 0.000001)
		{
			return false;
		}
	}
	return true;
}

bool HasLegacyWhiteBackground(const TSharedRef<FJsonObject>& StyleObject)
{
	const TArray<TSharedPtr<FJsonValue>>* BackgroundColor = nullptr;
	return StyleObject->TryGetArrayField(TEXT("background_color"), BackgroundColor)
		&& BackgroundColor != nullptr
		&& IsColorArray(*BackgroundColor, 1.0, 1.0, 1.0, 1.0);
}

bool HasBackgroundColor(const TSharedRef<FJsonObject>& StyleObject)
{
	const TArray<TSharedPtr<FJsonValue>>* BackgroundColor = nullptr;
	return StyleObject->TryGetArrayField(TEXT("background_color"), BackgroundColor)
		&& BackgroundColor != nullptr
		&& BackgroundColor->Num() >= 4;
}

void NormalizePanelBackgroundColor(const TSharedRef<FJsonObject>& StyleObject)
{
	if (!HasBackgroundColor(StyleObject) || HasLegacyWhiteBackground(StyleObject))
	{
		SetArrayField(StyleObject, TEXT("background_color"), 0.0, 0.0, 0.0, 0.1);
	}
}

TSharedRef<FJsonObject> EnsureObjectField(const TSharedRef<FJsonObject>& JsonObject, const TCHAR* FieldName)
{
	const TSharedPtr<FJsonObject>* ObjectValue = nullptr;
	if (JsonObject->TryGetObjectField(FStringView(FieldName), ObjectValue) && ObjectValue != nullptr && ObjectValue->IsValid())
	{
		return (*ObjectValue).ToSharedRef();
	}

	const TSharedRef<FJsonObject> NewObject = MakeShared<FJsonObject>();
	JsonObject->SetObjectField(FieldName, NewObject);
	return NewObject;
}

FString GetStringFieldOrEmpty(const TSharedRef<FJsonObject>& JsonObject, const TCHAR* FieldName)
{
	FString Value;
	JsonObject->TryGetStringField(FieldName, Value);
	return Value;
}

bool IsGeneratedAgsSpec(const TSharedRef<FJsonObject>& Spec)
{
	FString AssetPath;
	return Spec->TryGetStringField(TEXT("asset_path"), AssetPath)
		&& AssetPath.StartsWith(TEXT("/Game/AGS/UI/Generated/"));
}

FString SelectButtonPresetName(const FString& WidgetType, const FString& Name, const FString& ClassPath)
{
	const FString Combined = FString::Printf(TEXT("%s %s %s"), *WidgetType, *Name, *ClassPath).ToLower();
	if (Combined.Contains(TEXT("danger")) || Combined.Contains(TEXT("delete")) || Combined.Contains(TEXT("remove")))
	{
		return TEXT("dangerButton");
	}
	if (Combined.Contains(TEXT("secondary")) || Combined.Contains(TEXT("cancel")) || Combined.Contains(TEXT("tab")))
	{
		return TEXT("secondaryButton");
	}
	return TEXT("primaryButton");
}

FString SelectBorderPresetName(const FString& Name)
{
	const FString LowerName = Name.ToLower();
	return (LowerName.Contains(TEXT("card")) || LowerName.Contains(TEXT("item")) || LowerName.Contains(TEXT("row")))
		? TEXT("card")
		: TEXT("panel");
}

void ApplyPresetStyle(const TSharedRef<FJsonObject>& StyleObject, const FString& PresetName)
{
	if (PresetName == TEXT("input"))
	{
		SetArrayField(StyleObject, TEXT("background_color"), 1.0, 1.0, 1.0, 1.0);
		SetArrayField(StyleObject, TEXT("color"), 0.0, 0.0, 0.0, 1.0);
		SetArrayField(StyleObject, TEXT("hint_color"), 0.45, 0.49, 0.56, 1.0);
		StyleObject->SetNumberField(TEXT("corner_radius"), 6.0);
		SetArrayField(StyleObject, TEXT("border_color"), 0.31, 0.36, 0.43, 1.0);
		StyleObject->SetNumberField(TEXT("border_width"), 1.0);
	}
	else if (PresetName == TEXT("primaryButton"))
	{
		SetArrayField(StyleObject, TEXT("color"), 0.043, 0.424, 1.0, 1.0);
		SetArrayField(StyleObject, TEXT("hover_color"), 0.031, 0.341, 0.86, 1.0);
		SetArrayField(StyleObject, TEXT("pressed_color"), 0.022, 0.251, 0.66, 1.0);
		StyleObject->SetNumberField(TEXT("corner_radius"), 6.0);
		SetArrayField(StyleObject, TEXT("border_color"), 0.043, 0.424, 1.0, 1.0);
		StyleObject->SetNumberField(TEXT("border_width"), 1.0);
	}
	else if (PresetName == TEXT("secondaryButton"))
	{
		SetArrayField(StyleObject, TEXT("color"), 1.0, 1.0, 1.0, 1.0);
		SetArrayField(StyleObject, TEXT("hover_color"), 0.94, 0.97, 1.0, 1.0);
		SetArrayField(StyleObject, TEXT("pressed_color"), 0.89, 0.94, 1.0, 1.0);
		StyleObject->SetNumberField(TEXT("corner_radius"), 6.0);
		SetArrayField(StyleObject, TEXT("border_color"), 0.043, 0.424, 1.0, 1.0);
		StyleObject->SetNumberField(TEXT("border_width"), 1.0);
	}
	else if (PresetName == TEXT("dangerButton"))
	{
		SetArrayField(StyleObject, TEXT("color"), 0.89, 0.14, 0.2, 1.0);
		SetArrayField(StyleObject, TEXT("hover_color"), 0.75, 0.09, 0.13, 1.0);
		SetArrayField(StyleObject, TEXT("pressed_color"), 0.62, 0.07, 0.11, 1.0);
		StyleObject->SetNumberField(TEXT("corner_radius"), 6.0);
		SetArrayField(StyleObject, TEXT("border_color"), 0.89, 0.14, 0.2, 1.0);
		StyleObject->SetNumberField(TEXT("border_width"), 1.0);
	}
	else if (PresetName == TEXT("panel") || PresetName == TEXT("card"))
	{
		SetArrayField(StyleObject, TEXT("background_color"), 1.0, 1.0, 1.0, 1.0);
		StyleObject->SetNumberField(TEXT("corner_radius"), 8.0);
		SetArrayField(StyleObject, TEXT("border_color"), 0.84, 0.87, 0.92, 1.0);
		StyleObject->SetNumberField(TEXT("border_width"), 1.0);
	}
}

void SetThemePadding(const TSharedRef<FJsonObject>& Node, const FString& PaddingName)
{
	if (PaddingName == TEXT("controlPadding"))
	{
		SetArrayField(Node, TEXT("padding"), 8.0, 8.0, 8.0, 8.0);
	}
	else if (PaddingName == TEXT("cardPadding"))
	{
		SetArrayField(Node, TEXT("padding"), 12.0, 12.0, 12.0, 12.0);
	}
	else if (PaddingName == TEXT("panelPadding"))
	{
		SetArrayField(Node, TEXT("padding"), 16.0, 16.0, 16.0, 16.0);
	}
}

void EnsureSlotPadding(const TSharedPtr<FJsonObject>& ChildObject, const double Left, const double Top, const double Right, const double Bottom)
{
	if (!ChildObject.IsValid())
	{
		return;
	}

	TSharedRef<FJsonObject> SlotObject = EnsureObjectField(ChildObject.ToSharedRef(), TEXT("slot"));
	if (!SlotObject->HasTypedField<EJson::Array>(TEXT("padding")))
	{
		SetArrayField(SlotObject, TEXT("padding"), Left, Top, Right, Bottom);
	}
}

void NormalizeGeneratedAgsNode(const TSharedRef<FJsonObject>& Node, const bool bIsRoot = true)
{
	const FString WidgetType = GetStringFieldOrEmpty(Node, TEXT("type"));
	const FString Name = GetStringFieldOrEmpty(Node, TEXT("name"));
	const FString ClassPath = GetStringFieldOrEmpty(Node, TEXT("class_path"));

	if (WidgetType == TEXT("TextBlock"))
	{
		SetArrayField(EnsureObjectField(Node, TEXT("style")), TEXT("color"), 0.05, 0.06, 0.08, 1.0);
	}
	else if (WidgetType == TEXT("EditableTextBox"))
	{
		ApplyPresetStyle(EnsureObjectField(Node, TEXT("style")), TEXT("input"));
		SetThemePadding(Node, TEXT("controlPadding"));
	}
	else if (WidgetType == TEXT("Button"))
	{
		ApplyPresetStyle(EnsureObjectField(Node, TEXT("style")), SelectButtonPresetName(WidgetType, Name, ClassPath));
		SetThemePadding(Node, TEXT("controlPadding"));
	}
	else if (WidgetType == TEXT("Border"))
	{
		const FString PresetName = SelectBorderPresetName(Name);
		const TSharedRef<FJsonObject> StyleObject = EnsureObjectField(Node, TEXT("style"));
		const bool bUseProjectPanelBackground = bIsRoot && Name == TEXT("PanelBackground");
		bool bHadBackgroundColor = false;
		TArray<TSharedPtr<FJsonValue>> ExistingBackgroundColor;
		if (bUseProjectPanelBackground)
		{
			const TArray<TSharedPtr<FJsonValue>>* BackgroundColor = nullptr;
			bHadBackgroundColor = StyleObject->TryGetArrayField(TEXT("background_color"), BackgroundColor)
				&& BackgroundColor != nullptr
				&& BackgroundColor->Num() >= 4;
			if (bHadBackgroundColor)
			{
				ExistingBackgroundColor = *BackgroundColor;
			}
		}
		ApplyPresetStyle(StyleObject, PresetName);
		if (bUseProjectPanelBackground)
		{
			if (bHadBackgroundColor)
			{
				StyleObject->SetArrayField(TEXT("background_color"), ExistingBackgroundColor);
			}
			else
			{
				NormalizePanelBackgroundColor(StyleObject);
			}
		}
		SetThemePadding(Node, PresetName == TEXT("card") ? TEXT("cardPadding") : TEXT("panelPadding"));
	}
	else if (WidgetType == TEXT("AGSBaseButton")
		|| WidgetType == TEXT("AGSButton")
		|| WidgetType == TEXT("AGSSecondaryButton")
		|| WidgetType == TEXT("AGSDangerButton")
		|| WidgetType == TEXT("AGSIconButton")
		|| WidgetType == TEXT("AGSTextInput")
		|| WidgetType == TEXT("AGSPasswordInput")
		|| WidgetType == TEXT("AGSSearchInput"))
	{
		SetThemePadding(Node, TEXT("controlPadding"));
	}

	if (WidgetType == TEXT("ListView") || WidgetType == TEXT("TileView"))
	{
		Node->SetNumberField(TEXT("horizontal_entry_spacing"), 4.0);
		Node->SetNumberField(TEXT("vertical_entry_spacing"), 4.0);
	}

	const TArray<TSharedPtr<FJsonValue>>* Children = nullptr;
	if (Node->TryGetArrayField(TEXT("children"), Children))
	{
		for (const TSharedPtr<FJsonValue>& ChildValue : *Children)
		{
			const TSharedPtr<FJsonObject> ChildObject = ChildValue.IsValid() ? ChildValue->AsObject() : nullptr;
			if (ChildObject.IsValid())
			{
				if (WidgetType == TEXT("VerticalBox"))
				{
					EnsureSlotPadding(ChildObject, 0.0, 0.0, 0.0, 8.0);
				}
				else if (WidgetType == TEXT("HorizontalBox"))
				{
					EnsureSlotPadding(ChildObject, 0.0, 0.0, 8.0, 0.0);
				}
				else if (WidgetType == TEXT("WrapBox"))
				{
					EnsureSlotPadding(ChildObject, 0.0, 0.0, 8.0, 8.0);
				}
				NormalizeGeneratedAgsNode(ChildObject.ToSharedRef(), false);
			}
		}
	}
}

bool NormalizeGeneratedAgsTheme(const TSharedRef<FJsonObject>& Spec)
{
	if (!IsGeneratedAgsSpec(Spec))
	{
		return false;
	}

	const TSharedPtr<FJsonObject>* Root = nullptr;
	if (Spec->TryGetObjectField(TEXT("root"), Root) && Root != nullptr && Root->IsValid())
	{
		NormalizeGeneratedAgsNode((*Root).ToSharedRef());
		return true;
	}

	return false;
}

void VerifyAndFinalizeReport(const FString& AssetPath, const TSharedRef<FJsonObject>& Report, const FString& SpecJson = TEXT(""))
{
	TArray<FString> WidgetNames;
	TArray<FString> CollectionEntryAssignments;
	TArray<FString> WidgetClassAssignments;
	TArray<FString> BindingAssignments;
	FString Error;

	if (!AssetPath.IsEmpty() && !HasErrors(Report))
	{
		if (!UEditorAssetLibrary::SaveAsset(AssetPath, false))
		{
			AddError(Report, TEXT("save_failed"), AssetPath);
		}
		else if (UAccelByteUIToolsLibrary::ReadWidgetBlueprintHierarchy(AssetPath, WidgetNames, Error) <= 0 || !Error.IsEmpty())
		{
			AddError(Report, TEXT("verify_failed"), Error);
		}
		else if (!SpecJson.IsEmpty()
			&& !UAccelByteUIToolsLibrary::VerifyWidgetBlueprintCollectionEntries(AssetPath, SpecJson, CollectionEntryAssignments, Error))
		{
			AddError(Report, TEXT("verify_failed"), Error);
		}
		else if (!SpecJson.IsEmpty()
			&& !UAccelByteUIToolsLibrary::VerifyWidgetBlueprintClasses(AssetPath, SpecJson, WidgetClassAssignments, Error))
		{
			AddError(
				Report,
				Error.Contains(TEXT("stale Live Coding")) ? TEXT("stale_live_coding_class") : TEXT("verify_failed"),
				Error);
		}
	}

	Report->SetStringField(TEXT("asset_path"), AssetPath);
	Report->SetNumberField(TEXT("verified_widget_count"), WidgetNames.Num());

	TArray<TSharedPtr<FJsonValue>> WidgetNameValues;
	for (const FString& WidgetName : WidgetNames)
	{
		WidgetNameValues.Add(MakeShared<FJsonValueString>(WidgetName));
	}
	Report->SetArrayField(TEXT("verified_widget_names"), WidgetNameValues);
	AddCollectionEntryAssignments(Report, CollectionEntryAssignments);
	AddWidgetClassAssignments(Report, WidgetClassAssignments);
	AddBackingBindingAssignments(Report, BindingAssignments);
	Report->SetBoolField(TEXT("ok"), !HasErrors(Report));
}

bool HandleHealthRequest(const FHttpServerRequest&, const FHttpResultCallback& OnComplete)
{
	const TSharedRef<FJsonObject> Body = MakeShared<FJsonObject>();
	Body->SetBoolField(TEXT("ok"), true);
	Body->SetStringField(TEXT("service"), TEXT("AccelByteUITools"));
	CompleteJson(OnComplete, Body);
	return true;
}

bool CompleteResolveRequest(
	const TSharedPtr<FJsonObject>& Spec,
	const FString& AssetPath,
	const FString& SpecJson,
	const TSharedRef<FJsonObject>& Report,
	const FHttpResultCallback& OnComplete)
{
	FString Error;
	TArray<FString> PreflightWidgetClassAssignments;
	if (!UAccelByteUIToolsLibrary::VerifyExpectedWidgetClassesStable(SpecJson, PreflightWidgetClassAssignments, Error))
	{
		AddError(
			Report,
			Error.Contains(TEXT("stale Live Coding")) ? TEXT("stale_live_coding_class") : TEXT("verify_failed"),
			Error);
	}

	Report->SetBoolField(TEXT("resolve_only"), true);
	Report->SetBoolField(TEXT("verify_only"), true);
	Report->SetStringField(TEXT("asset_path"), AssetPath);
	Report->SetNumberField(TEXT("verified_widget_count"), 0);
	Report->SetArrayField(TEXT("verified_widget_names"), TArray<TSharedPtr<FJsonValue>>());
	AddExpectedCollectionEntries(Report, Spec);
	AddCollectionEntryAssignments(Report, TArray<FString>());
	AddWidgetClassAssignments(Report, PreflightWidgetClassAssignments);
	AddBackingBindingAssignments(Report, TArray<FString>());
	Report->SetBoolField(TEXT("ok"), !HasErrors(Report));
	CompleteJson(OnComplete, Report);
	return true;
}

void CollectBlueprintPathsFromNode(const TSharedPtr<FJsonObject>& Node, TSet<FString>& OutPaths)
{
	if (!Node.IsValid()) return;

	auto TryAdd = [&](const FString& Path) {
		if (!Path.IsEmpty() && !Path.StartsWith(TEXT("/Script/")))
			OutPaths.Add(Path);
	};

	FString ClassPath;
	if (Node->TryGetStringField(TEXT("class_path"), ClassPath)) TryAdd(ClassPath);

	FString EntryClass;
	if (Node->TryGetStringField(TEXT("entry_widget_class"), EntryClass)) TryAdd(EntryClass);

	const TArray<TSharedPtr<FJsonValue>>* Children;
	if (Node->TryGetArrayField(TEXT("children"), Children))
	{
		for (const TSharedPtr<FJsonValue>& Child : *Children)
		{
			if (Child.IsValid() && Child->Type == EJson::Object)
				CollectBlueprintPathsFromNode(Child->AsObject(), OutPaths);
		}
	}
}

// Load and compile any source-only Blueprint widgets referenced by the spec before
// widget-tree construction begins. Uses FKismetEditorUtilities::CompileBlueprint
// (initial-compilation API) rather than FBlueprintCompilationManager::QueueForCompilation
// (recompilation API) because these blueprints have no GeneratedClass yet. QueueForCompilation
// creates an FBlueprintCompileReinstancer that expects a non-null ClassToReinstance and
// crashes (check(ClassToReinstance) at KismetReinstanceUtilities.cpp:639) when given a
// blueprint whose GeneratedClass is null.
void PreCompileBlueprintDependencies(const TSharedRef<FJsonObject>& Spec)
{
	TSet<FString> ClassPaths;
	const TSharedPtr<FJsonObject>* Root;
	if (Spec->TryGetObjectField(TEXT("root"), Root))
		CollectBlueprintPathsFromNode(*Root, ClassPaths);

	TArray<UBlueprint*> ToCompile;
	for (const FString& ClassPath : ClassPaths)
	{
		if (LoadClass<UWidget>(nullptr, *ClassPath)) continue;

		int32 DotIndex;
		if (!ClassPath.FindLastChar(TEXT('.'), DotIndex)) continue;
		const FString AssetPath = ClassPath.Left(DotIndex);

		// Use Cast<UBlueprint> (not Cast<UWidgetBlueprint>) — matches the pattern in
		// ResolveWidgetClass that successfully loads these blueprints (BP=valid).
		// Cast<UWidgetBlueprint> can silently return null in this compilation unit.
		if (UBlueprint* WB = Cast<UBlueprint>(
			StaticLoadObject(UBlueprint::StaticClass(), nullptr, *AssetPath)))
		{
			bool bNeedsCompile = !WB->GeneratedClass || !WB->IsUpToDate();
			if (!bNeedsCompile)
			{
				// Also recompile when GeneratedClass exists but is still unreachable via
				// LoadClass — this happens after a plugin folder rename where the compiled
				// class is registered under the old package path, not the current one.
				bNeedsCompile = (LoadClass<UWidget>(nullptr, *ClassPath) == nullptr);
				if (bNeedsCompile)
				{
					UE_LOG(LogAccelByteUIToolsBridge, Warning,
						TEXT("PreCompile: forcing recompile of %s — class_path unreachable despite non-null GeneratedClass (%s)"),
						*AssetPath, *WB->GeneratedClass->GetPathName());
				}
			}
			if (bNeedsCompile)
			{
				UE_LOG(LogAccelByteUIToolsBridge, Log,
					TEXT("PreCompile: queuing %s (GenClass=%s)"), *AssetPath,
					WB->GeneratedClass ? TEXT("stale-or-wrong-path") : TEXT("null"));
				ToCompile.Add(WB);
			}
		}
	}

	if (ToCompile.IsEmpty()) return;

	for (UBlueprint* WB : ToCompile)
	{
		// If the parent class is stale after a C++ rebuild (CLASS_NewerVersionExists),
		// resolve it to the current version via path lookup before compiling.
		// CompileBlueprint silently skips blueprints whose ParentClass is stale.
		if (WB->ParentClass && WB->ParentClass->HasAnyClassFlags(CLASS_NewerVersionExists))
		{
			if (UClass* CurrentParent = FindObject<UClass>(nullptr, *WB->ParentClass->GetPathName()))
			{
				if (!CurrentParent->HasAnyClassFlags(CLASS_NewerVersionExists))
				{
					UE_LOG(LogAccelByteUIToolsBridge, Warning,
						TEXT("PreCompile: refreshed stale ParentClass for %s: %s -> %s"),
						*WB->GetName(), *WB->ParentClass->GetName(), *CurrentParent->GetName());
					WB->ParentClass = CurrentParent;
				}
			}
		}
		FKismetEditorUtilities::CompileBlueprint(WB, EBlueprintCompileOptions::SkipGarbageCollection);
		UE_LOG(LogAccelByteUIToolsBridge, Log,
			TEXT("PreCompile: compiled %s -> GenClass=%s"), *WB->GetName(),
			WB->GeneratedClass ? *WB->GeneratedClass->GetName() : TEXT("NULL"));
	}
}

bool HandleGenerateRequest(const FHttpServerRequest& Request, const FHttpResultCallback& OnComplete)
{
	TSharedPtr<FJsonObject> Body;
	FString Error;
	const TSharedRef<FJsonObject> Report = BuildBaseReport();
	if (!ParseRequestBody(Request, Body, Error))
	{
		AddError(Report, TEXT("invalid_request"), Error);
		VerifyAndFinalizeReport(TEXT(""), Report);
		CompleteJson(OnComplete, Report, EHttpServerResponseCodes::BadRequest);
		return true;
	}

	TSharedPtr<FJsonObject> Spec;
	FString AssetPath;
	FString ParentClassPath;
	if (!RequireObjectField(Body.ToSharedRef(), TEXT("spec"), Spec, Report)
		|| !RequireStringField(Spec.ToSharedRef(), TEXT("asset_path"), AssetPath, Report)
		|| !RequireStringField(Spec.ToSharedRef(), TEXT("parent_class"), ParentClassPath, Report))
	{
		VerifyAndFinalizeReport(AssetPath, Report);
		CompleteJson(OnComplete, Report, EHttpServerResponseCodes::BadRequest);
		return true;
	}

	bool bForce = false;
	Body->TryGetBoolField(TEXT("force"), bForce);
	bool bVerifyOnly = false;
	Body->TryGetBoolField(TEXT("verify_only"), bVerifyOnly);
	const bool bNormalizedTheme = NormalizeGeneratedAgsTheme(Spec.ToSharedRef());
	const FString SpecJson = ToJsonText(Spec.ToSharedRef());
	TArray<FString> PreflightWidgetClassAssignments;
	TArray<FString> PreflightBindingAssignments;
	if (bNormalizedTheme)
	{
		Report->SetBoolField(TEXT("theme_normalized"), true);
		Report->SetStringField(TEXT("normalized_by"), TEXT("AccelByteUIToolsEditorBridge"));
		Report->SetStringField(TEXT("normalized_spec_hash"), FString::Printf(TEXT("%08x"), FCrc::StrCrc32(*SpecJson)));
	}

	// Pre-compile any source-only Blueprint widget dependencies before PopulateWidgetBlueprintFromJson.
	if (!bVerifyOnly)
	{
		PreCompileBlueprintDependencies(Spec.ToSharedRef());
	}

	if (bVerifyOnly)
	{
		return CompleteResolveRequest(Spec, AssetPath, SpecJson, Report, OnComplete);
	}
	else if (!UAccelByteUIToolsLibrary::VerifyExpectedWidgetClassesStable(SpecJson, PreflightWidgetClassAssignments, Error))
	{
		AddError(
			Report,
			Error.Contains(TEXT("stale Live Coding")) ? TEXT("stale_live_coding_class") : TEXT("verify_failed"),
			Error);
	}
	else if (!UAccelByteUIToolsLibrary::VerifyParentWidgetBindings(ParentClassPath, SpecJson, PreflightBindingAssignments, Error))
	{
		AddError(Report, TEXT("backing_binding_mismatch"), Error);
	}
	else if (!UAccelByteUIToolsLibrary::CreateWidgetBlueprint(AssetPath, ParentClassPath, bForce, Error))
	{
		if (Error.StartsWith(TEXT("Parent class could not be loaded:")))
		{
			AddParentClassLoadError(Report, ParentClassPath, Error);
		}
		else
		{
			AddError(Report, TEXT("create_failed"), Error);
		}
	}
	else if (!UAccelByteUIToolsLibrary::PopulateWidgetBlueprintFromJson(AssetPath, SpecJson, Error))
	{
		AddError(Report, TEXT("populate_failed"), Error);
	}

	VerifyAndFinalizeReport(AssetPath, Report, SpecJson);
	if (!PreflightWidgetClassAssignments.IsEmpty() && HasErrors(Report))
	{
		AddWidgetClassAssignments(Report, PreflightWidgetClassAssignments);
	}
	if (!PreflightBindingAssignments.IsEmpty())
	{
		AddBackingBindingAssignments(Report, PreflightBindingAssignments);
	}
	CompleteJson(OnComplete, Report);
	return true;
}

bool HandleResolveRequest(const FHttpServerRequest& Request, const FHttpResultCallback& OnComplete)
{
	TSharedPtr<FJsonObject> Body;
	FString Error;
	const TSharedRef<FJsonObject> Report = BuildBaseReport();
	if (!ParseRequestBody(Request, Body, Error))
	{
		AddError(Report, TEXT("invalid_request"), Error);
		VerifyAndFinalizeReport(TEXT(""), Report);
		CompleteJson(OnComplete, Report, EHttpServerResponseCodes::BadRequest);
		return true;
	}

	TSharedPtr<FJsonObject> Spec;
	FString AssetPath;
	FString ParentClassPath;
	if (!RequireObjectField(Body.ToSharedRef(), TEXT("spec"), Spec, Report)
		|| !RequireStringField(Spec.ToSharedRef(), TEXT("asset_path"), AssetPath, Report)
		|| !RequireStringField(Spec.ToSharedRef(), TEXT("parent_class"), ParentClassPath, Report))
	{
		VerifyAndFinalizeReport(AssetPath, Report);
		CompleteJson(OnComplete, Report, EHttpServerResponseCodes::BadRequest);
		return true;
	}

	const bool bNormalizedTheme = NormalizeGeneratedAgsTheme(Spec.ToSharedRef());
	const FString SpecJson = ToJsonText(Spec.ToSharedRef());
	if (bNormalizedTheme)
	{
		Report->SetBoolField(TEXT("theme_normalized"), true);
		Report->SetStringField(TEXT("normalized_by"), TEXT("AccelByteUIToolsEditorBridge"));
		Report->SetStringField(TEXT("normalized_spec_hash"), FString::Printf(TEXT("%08x"), FCrc::StrCrc32(*SpecJson)));
	}

	return CompleteResolveRequest(Spec, AssetPath, SpecJson, Report, OnComplete);
}

bool HandlePatchRequest(const FHttpServerRequest& Request, const FHttpResultCallback& OnComplete)
{
	TSharedPtr<FJsonObject> Body;
	FString Error;
	const TSharedRef<FJsonObject> Report = BuildBaseReport();
	if (!ParseRequestBody(Request, Body, Error))
	{
		AddError(Report, TEXT("invalid_request"), Error);
		VerifyAndFinalizeReport(TEXT(""), Report);
		CompleteJson(OnComplete, Report, EHttpServerResponseCodes::BadRequest);
		return true;
	}

	FString AssetPath;
	if (!RequireStringField(Body.ToSharedRef(), TEXT("asset_path"), AssetPath, Report))
	{
		VerifyAndFinalizeReport(AssetPath, Report);
		CompleteJson(OnComplete, Report, EHttpServerResponseCodes::BadRequest);
		return true;
	}

	FString Op;
	Body->TryGetStringField(TEXT("op"), Op);
	if (Op == TEXT("set_widget_properties"))
	{
		FString WidgetName;
		TSharedPtr<FJsonObject> Properties;
		if (!RequireStringField(Body.ToSharedRef(), TEXT("widget_name"), WidgetName, Report)
			|| !RequireObjectField(Body.ToSharedRef(), TEXT("properties"), Properties, Report))
		{
			VerifyAndFinalizeReport(AssetPath, Report);
			CompleteJson(OnComplete, Report, EHttpServerResponseCodes::BadRequest);
			return true;
		}

		if (!UAccelByteUIToolsLibrary::UpdateWidgetPropertiesInWidgetBlueprintFromJson(AssetPath, WidgetName, ToJsonText(Properties.ToSharedRef()), Error))
		{
			AddError(Report, TEXT("patch_failed"), Error);
		}
		else
		{
			TArray<TSharedPtr<FJsonValue>> UpdatedWidgetNames;
			UpdatedWidgetNames.Add(MakeShared<FJsonValueString>(WidgetName));
			Report->SetArrayField(TEXT("updated_widget_names"), UpdatedWidgetNames);
		}
	}
	else
	{
		FString ParentWidgetName;
		TSharedPtr<FJsonObject> Widget;
		if (!RequireStringField(Body.ToSharedRef(), TEXT("parent_widget_name"), ParentWidgetName, Report)
			|| !RequireObjectField(Body.ToSharedRef(), TEXT("widget"), Widget, Report))
		{
			VerifyAndFinalizeReport(AssetPath, Report);
			CompleteJson(OnComplete, Report, EHttpServerResponseCodes::BadRequest);
			return true;
		}

		if (!UAccelByteUIToolsLibrary::AddWidgetToWidgetBlueprintFromJson(AssetPath, ParentWidgetName, ToJsonText(Widget.ToSharedRef()), Error))
		{
			AddError(Report, TEXT("patch_failed"), Error);
		}
	}

	VerifyAndFinalizeReport(AssetPath, Report);
	CompleteJson(OnComplete, Report);
	return true;
}

FString LiveCodingCompileResultToString(const ELiveCodingCompileResult Result)
{
	switch (Result)
	{
	case ELiveCodingCompileResult::Success:
		return TEXT("success");
	case ELiveCodingCompileResult::NoChanges:
		return TEXT("no_changes");
	case ELiveCodingCompileResult::InProgress:
		return TEXT("in_progress");
	case ELiveCodingCompileResult::CompileStillActive:
		return TEXT("compile_still_active");
	case ELiveCodingCompileResult::NotStarted:
		return TEXT("not_started");
	case ELiveCodingCompileResult::Failure:
		return TEXT("failure");
	case ELiveCodingCompileResult::Cancelled:
		return TEXT("cancelled");
	default:
		return TEXT("unknown");
	}
}

bool HandleLiveCodingCompileRequest(const FHttpServerRequest& Request, const FHttpResultCallback& OnComplete)
{
	TSharedPtr<FJsonObject> Body;
	FString Error;
	bool bWaitForCompletion = true;
	if (!Request.Body.IsEmpty())
	{
		if (!ParseRequestBody(Request, Body, Error))
		{
			const TSharedRef<FJsonObject> Report = BuildBaseReport();
			AddError(Report, TEXT("invalid_request"), Error);
			CompleteJson(OnComplete, Report, EHttpServerResponseCodes::BadRequest);
			return true;
		}

		Body->TryGetBoolField(TEXT("waitForCompletion"), bWaitForCompletion);
	}

	ILiveCodingModule* LiveCodingModule = FModuleManager::GetModulePtr<ILiveCodingModule>(LIVE_CODING_MODULE_NAME);
	if (LiveCodingModule == nullptr)
	{
		LiveCodingModule = FModuleManager::LoadModulePtr<ILiveCodingModule>(LIVE_CODING_MODULE_NAME);
	}

	const TSharedRef<FJsonObject> Report = MakeShared<FJsonObject>();
	if (LiveCodingModule == nullptr)
	{
		Report->SetBoolField(TEXT("ok"), false);
		Report->SetStringField(TEXT("status"), TEXT("module_unavailable"));
		Report->SetStringField(TEXT("message"), TEXT("Live Coding module is not available in this editor session."));
		CompleteJson(OnComplete, Report, EHttpServerResponseCodes::ServerError);
		return true;
	}

	ELiveCodingCompileResult CompileResult = ELiveCodingCompileResult::Failure;
	const ELiveCodingCompileFlags CompileFlags =
		bWaitForCompletion ? ELiveCodingCompileFlags::WaitForCompletion : ELiveCodingCompileFlags::None;
	const bool bCompileAccepted = LiveCodingModule->Compile(CompileFlags, &CompileResult);

	Report->SetBoolField(TEXT("ok"), bCompileAccepted);
	Report->SetBoolField(TEXT("waited"), bWaitForCompletion);
	Report->SetBoolField(TEXT("live_coding_enabled"), LiveCodingModule->IsEnabledForSession());
	Report->SetBoolField(TEXT("is_compiling"), LiveCodingModule->IsCompiling());
	Report->SetStringField(TEXT("status"), LiveCodingCompileResultToString(CompileResult));
	if (!bCompileAccepted)
	{
		Report->SetStringField(TEXT("message"), LiveCodingModule->GetEnableErrorText().ToString());
	}

	CompleteJson(OnComplete, Report);
	return true;
}
}

void FAccelByteUIToolsEditorModule::StartupModule()
{
	StartHttpBridge();
}

void FAccelByteUIToolsEditorModule::ShutdownModule()
{
	StopHttpBridge();
}

void FAccelByteUIToolsEditorModule::StartHttpBridge()
{
	FHttpServerModule& HttpServerModule = FHttpServerModule::Get();
	Router = HttpServerModule.GetHttpRouter(WidgetGeneratorBridgePort);
	if (!Router.IsValid())
	{
		UE_LOG(LogAccelByteUIToolsBridge, Warning, TEXT("AccelByteUITools bridge could not create HTTP router on port %u."), WidgetGeneratorBridgePort);
		return;
	}

	HealthRouteHandle = Router->BindRoute(
		FHttpPath(TEXT("/accelbyte-ui-tools/health")),
		EHttpServerRequestVerbs::VERB_GET,
		FHttpRequestHandler::CreateStatic(&HandleHealthRequest));

	GenerateRouteHandle = Router->BindRoute(
		FHttpPath(TEXT("/accelbyte-ui-tools/generate")),
		EHttpServerRequestVerbs::VERB_POST,
		FHttpRequestHandler::CreateStatic(&HandleGenerateRequest));

	ResolveRouteHandle = Router->BindRoute(
		FHttpPath(TEXT("/accelbyte-ui-tools/resolve")),
		EHttpServerRequestVerbs::VERB_POST,
		FHttpRequestHandler::CreateStatic(&HandleResolveRequest));

	PatchRouteHandle = Router->BindRoute(
		FHttpPath(TEXT("/accelbyte-ui-tools/patch")),
		EHttpServerRequestVerbs::VERB_POST,
		FHttpRequestHandler::CreateStatic(&HandlePatchRequest));

	LiveCodingCompileRouteHandle = Router->BindRoute(
		FHttpPath(TEXT("/unreal/live-coding/compile")),
		EHttpServerRequestVerbs::VERB_POST,
		FHttpRequestHandler::CreateStatic(&HandleLiveCodingCompileRequest));

	if (!HealthRouteHandle.IsValid() || !GenerateRouteHandle.IsValid() || !ResolveRouteHandle.IsValid() || !PatchRouteHandle.IsValid() || !LiveCodingCompileRouteHandle.IsValid())
	{
		UE_LOG(LogAccelByteUIToolsBridge, Warning, TEXT("AccelByteUITools bridge could not bind all routes on port %u."), WidgetGeneratorBridgePort);
		StopHttpBridge();
		return;
	}

	// UE's HTTPServer module exposes listener startup as process-global state. StartAllListeners is required
	// for this route to become reachable; this module only owns and unbinds its route handles on shutdown.
	HttpServerModule.StartAllListeners();

	TSharedPtr<IHttpRouter> ListeningRouter = HttpServerModule.GetHttpRouter(WidgetGeneratorBridgePort, true);
	if (!ListeningRouter.IsValid())
	{
		UE_LOG(LogAccelByteUIToolsBridge, Warning, TEXT("AccelByteUITools bridge could not start listening on port %u."), WidgetGeneratorBridgePort);
		StopHttpBridge();
		return;
	}

	UE_LOG(LogAccelByteUIToolsBridge, Display, TEXT("AccelByteUITools bridge route registered on http://127.0.0.1:%u."), WidgetGeneratorBridgePort);
}

void FAccelByteUIToolsEditorModule::StopHttpBridge()
{
	bool bHadBridgeRoutes = false;
	if (Router.IsValid())
	{
		if (HealthRouteHandle.IsValid())
		{
			Router->UnbindRoute(HealthRouteHandle);
			HealthRouteHandle.Reset();
			bHadBridgeRoutes = true;
		}
		if (GenerateRouteHandle.IsValid())
		{
			Router->UnbindRoute(GenerateRouteHandle);
			GenerateRouteHandle.Reset();
			bHadBridgeRoutes = true;
		}
		if (ResolveRouteHandle.IsValid())
		{
			Router->UnbindRoute(ResolveRouteHandle);
			ResolveRouteHandle.Reset();
			bHadBridgeRoutes = true;
		}
		if (PatchRouteHandle.IsValid())
		{
			Router->UnbindRoute(PatchRouteHandle);
			PatchRouteHandle.Reset();
			bHadBridgeRoutes = true;
		}
		if (LiveCodingCompileRouteHandle.IsValid())
		{
			Router->UnbindRoute(LiveCodingCompileRouteHandle);
			LiveCodingCompileRouteHandle.Reset();
			bHadBridgeRoutes = true;
		}
		Router.Reset();
	}

	if (bHadBridgeRoutes)
	{
		UE_LOG(LogAccelByteUIToolsBridge, Display, TEXT("AccelByteUITools bridge stopped."));
	}
}

#undef LOCTEXT_NAMESPACE

IMPLEMENT_MODULE(FAccelByteUIToolsEditorModule, AccelByteUIToolsEditor)
